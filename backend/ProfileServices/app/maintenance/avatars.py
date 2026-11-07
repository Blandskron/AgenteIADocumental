import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator
from sqlalchemy import create_engine, text, update
from sqlalchemy.orm import Session

from app.domain.avatars import MAX_UPLOAD_BYTES, normalize_avatar
from app.infrastructure.database.models import UserProfileModel
from app.infrastructure.legacy_avatar_files import open_directory, read_regular_file


class PruneEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    user_id: int = Field(ge=1, le=2**63 - 1)
    expected_version: int = Field(ge=1, le=2**63 - 2)


class ImportEntry(PruneEntry):
    source: str = Field(pattern=r"^[0-9a-f]{32}\.(jpg|jpeg|png|webp)$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    legacy_url: str = Field(max_length=2048)

    @model_validator(mode="after")
    def match_reference(self):
        url = urlsplit(self.legacy_url)
        if (url.scheme not in {"", "http", "https"} or url.query or url.fragment or url.username or url.password
                or (url.scheme and not url.hostname) or (not url.scheme and url.netloc)
                or url.path != "/static/" + self.source):
            raise ValueError("Legacy reference does not match the reviewed source.")
        return self


def manifest(path: Path, importing: bool):
    entries = TypeAdapter(list[ImportEntry] if importing else list[PruneEntry]).validate_json(
        read_regular_file(path.parent, path.name, 65536),
    )
    if not 1 <= len(entries) <= 100 or len({entry.user_id for entry in entries}) != len(entries):
        raise ValueError("Manifest must contain 1-100 distinct owners.")
    if importing and len({entry.source for entry in entries}) != len(entries):
        raise ValueError("Shared sources require separate ownership review.")
    return sorted(entries, key=lambda entry: entry.user_id)


def inventory(session: Session, directory: Path) -> dict:
    if directory == Path("/"):
        raise ValueError("A dedicated legacy directory is required.")
    descriptor = open_directory(directory)
    try:
        files = 0
        with os.scandir(descriptor) as entries:
            for entry in entries:
                files += 1
                if files > 10000:
                    raise ValueError("Inventory exceeds the review batch limit.")
        counts = session.execute(text("""
            SELECT count(*) FILTER (WHERE avatar_ready) AS private_avatars,
                   count(*) FILTER (WHERE NOT avatar_ready AND coalesce(profile_picture_url,'') <> '') AS legacy_references,
                   count(*) FILTER (WHERE avatar_ready AND NOT EXISTS (
                       SELECT 1 FROM public.auth_user u WHERE u.id::text=p.user_id)) AS orphan_avatars
            FROM public.user_profiles p
        """)).mappings().one()
        shared = session.scalar(text("""
            SELECT count(*) FROM (
                SELECT substring(profile_picture_url FROM '/static/([0-9a-f]{32}[.][a-z]+)$') AS source
                FROM user_profiles WHERE NOT avatar_ready
                GROUP BY source HAVING count(*) > 1
            ) reviewed WHERE source IS NOT NULL
        """))
        return {**dict(counts), "legacy_directory_entries": files, "shared_source_groups": shared}
    finally:
        os.close(descriptor)


def import_avatars(session: Session, directory: Path, entries: list[ImportEntry], *, apply: bool = False):
    if directory == Path("/"):
        raise ValueError("A dedicated legacy directory is required.")
    prepared = []
    for entry in entries:
        content = read_regular_file(directory, entry.source, MAX_UPLOAD_BYTES)
        if hashlib.sha256(content).hexdigest() != entry.sha256:
            raise ValueError("Reviewed source checksum changed.")
        prepared.append((entry, normalize_avatar(content)))
    eligible = 0
    for entry, normalized in prepared:
        current = session.scalar(text("""
            SELECT EXISTS (SELECT 1 FROM public.auth_user WHERE id=:id AND is_active IS TRUE
        """ + (" FOR SHARE" if apply else "") + ")"), {"id": entry.user_id})
        query = update(UserProfileModel).where(
            UserProfileModel.user_id == str(entry.user_id), UserProfileModel.version == entry.expected_version,
            UserProfileModel.avatar_ready.is_(False), UserProfileModel.avatar_data.is_(None),
            UserProfileModel.profile_picture_url == entry.legacy_url,
        )
        if current:
            if apply:
                eligible += len(session.scalars(query.values(avatar_data=normalized, avatar_ready=True,
                    profile_picture_url=None, version=UserProfileModel.version + 1).returning(UserProfileModel.profile_id)).all())
            else:
                eligible += int(session.scalar(text("""
                    SELECT EXISTS (SELECT 1 FROM user_profiles WHERE user_id=:id AND version=:version
                        AND NOT avatar_ready AND avatar_data IS NULL AND profile_picture_url=:url)
                """), {"id": str(entry.user_id), "version": entry.expected_version, "url": entry.legacy_url}))
    return {"reviewed": len(entries), "eligible": eligible, "imported": eligible if apply else 0}


def prune_avatars(session: Session, entries: list[PruneEntry], *, apply: bool = False):
    eligible = 0
    for entry in entries:
        parameters = {"id": str(entry.user_id), "version": entry.expected_version}
        where = """user_id=:id AND version=:version AND avatar_ready
            AND NOT EXISTS (SELECT 1 FROM public.auth_user u WHERE u.id::text=user_profiles.user_id)"""
        if apply:
            eligible += len(session.execute(text("""
                UPDATE user_profiles SET avatar_data=NULL,avatar_ready=FALSE,profile_picture_url=NULL,version=version+1
                WHERE """ + where + " RETURNING profile_id"), parameters).all())
        else:
            eligible += int(session.scalar(text("SELECT EXISTS (SELECT 1 FROM user_profiles WHERE " + where + ")"), parameters))
    return {"reviewed": len(entries), "eligible": eligible, "cleared": eligible if apply else 0}


def main():
    parser = argparse.ArgumentParser(description="Reviewed avatar maintenance; defaults to dry-run.")
    parser.add_argument("operation", choices=["inventory", "import", "prune"])
    parser.add_argument("--legacy-dir", type=Path, default=Path("/legacy-avatars"))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    engine = None
    try:
        engine = create_engine(os.environ["PROFILE_MIGRATION_DATABASE_URL"], hide_parameters=True,
                               connect_args={"connect_timeout": 5, "options": "-c statement_timeout=30000"})
        with Session(engine) as session, session.begin():
            if args.operation == "inventory":
                result = inventory(session, args.legacy_dir)
            else:
                if args.manifest is None or not args.manifest.is_absolute():
                    raise ValueError("An absolute reviewed manifest is required.")
                entries = manifest(args.manifest, args.operation == "import")
                result = (import_avatars(session, args.legacy_dir, entries, apply=args.apply)
                          if args.operation == "import" else prune_avatars(session, entries, apply=args.apply))
        print(json.dumps(result, sort_keys=True))
    except Exception:
        print("Avatar maintenance failed; no batch changes committed.", file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
