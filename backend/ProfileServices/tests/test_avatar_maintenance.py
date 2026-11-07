import hashlib
import json
import os
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.infrastructure.legacy_avatar_files import read_regular_file
from app.maintenance.avatars import ImportEntry, PruneEntry, import_avatars, manifest, prune_avatars
from tests.test_avatars import image_bytes


def test_confined_sources_reject_links_special_files_and_oversize(tmp_path):
    source = tmp_path / "source"
    source.write_bytes(b"synthetic")
    assert read_regular_file(tmp_path, "source", 9) == b"synthetic"
    with pytest.raises(ValueError):
        read_regular_file(tmp_path, "source", 8)
    for name in ("../source", "/source", "a\\source", ".."):
        with pytest.raises(ValueError):
            read_regular_file(tmp_path, name, 100)
    (tmp_path / "link").symlink_to(source)
    with pytest.raises(OSError):
        read_regular_file(tmp_path, "link", 100)
    os.link(source, tmp_path / "hard")
    with pytest.raises(ValueError):
        read_regular_file(tmp_path, "source", 100)
    os.mkfifo(tmp_path / "pipe")
    with pytest.raises(ValueError):
        read_regular_file(tmp_path, "pipe", 100)
    (tmp_path / "ancestor").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(OSError):
        read_regular_file(tmp_path / "ancestor", "source", 100)


def reviewed(tmp_path, profile_id):
    content = image_bytes()
    source = "a" * 32 + ".png"
    (tmp_path / source).write_bytes(content)
    return ImportEntry(user_id=int(profile_id), expected_version=1, source=source,
                       sha256=hashlib.sha256(content).hexdigest(), legacy_url="/static/" + source)


def test_manifest_requires_distinct_reviewed_owners_and_sources(tmp_path, profile_id):
    entry = reviewed(tmp_path, profile_id)
    path = tmp_path / "reviewed.json"
    path.write_text(json.dumps([entry.model_dump()]))
    assert manifest(path, True) == [entry]
    for entries in ([entry.model_dump()] * 2, [], [{**entry.model_dump(), "source": "../source"}],
                    [entry.model_dump(), {**entry.model_dump(), "user_id": int(profile_id) + 1}]):
        path.write_text(json.dumps(entries))
        with pytest.raises(ValueError):
            manifest(path, True)


def test_import_is_explicit_versioned_and_dry_by_default(db_session, profile_id, tmp_path):
    entry = reviewed(tmp_path, profile_id)
    db_session.execute(text("INSERT INTO user_profiles(user_id,profile_picture_url) VALUES (:id,:url)"),
                       {"id": profile_id, "url": entry.legacy_url})
    assert import_avatars(db_session, tmp_path, [entry]) == {"reviewed": 1, "eligible": 1, "imported": 0}
    assert db_session.scalar(text("SELECT avatar_ready FROM user_profiles WHERE user_id=:id"), {"id": profile_id}) is False
    assert import_avatars(db_session, tmp_path, [entry], apply=True)["imported"] == 1
    row = db_session.execute(text("SELECT version,avatar_ready,avatar_data,profile_picture_url FROM user_profiles WHERE user_id=:id"), {"id": profile_id}).one()
    assert row.version == 2 and row.avatar_ready and row.avatar_data[:2] == b"\xff\xd8" and row.profile_picture_url is None
    assert import_avatars(db_session, tmp_path, [entry], apply=True)["imported"] == 0
    assert (tmp_path / entry.source).is_file()


def test_changed_source_rejects_entire_import_before_writes(db_session, profile_id, other_id, tmp_path):
    first = reviewed(tmp_path, profile_id)
    second = first.model_copy(update={"user_id": int(other_id), "source": "b" * 32 + ".png"})
    (tmp_path / second.source).write_bytes(b"changed")
    for entry in (first, second):
        db_session.execute(text("INSERT INTO user_profiles(user_id,profile_picture_url) VALUES (:id,:url)"),
                           {"id": str(entry.user_id), "url": entry.legacy_url})
    with pytest.raises(ValueError, match="checksum"):
        import_avatars(db_session, tmp_path, [first, second], apply=True)
    assert db_session.scalar(text("SELECT count(*) FROM user_profiles WHERE user_id IN (:a,:b) AND avatar_ready"),
                             {"a": profile_id, "b": other_id}) == 0


@pytest.mark.parametrize("condition", ["inactive", "version", "reference"])
def test_import_does_not_guess_ownership_or_overwrite(db_session, profile_id, tmp_path, condition):
    entry = reviewed(tmp_path, profile_id)
    db_session.execute(text("INSERT INTO user_profiles(user_id,profile_picture_url) VALUES (:id,:url)"),
                       {"id": profile_id, "url": entry.legacy_url})
    if condition == "inactive":
        db_session.execute(text("UPDATE auth_user SET is_active=FALSE WHERE id=:id"), {"id": int(profile_id)})
    elif condition == "version":
        entry = entry.model_copy(update={"expected_version": 2})
    else:
        entry = entry.model_copy(update={"legacy_url": "https://other.invalid" + entry.legacy_url})
    assert import_avatars(db_session, tmp_path, [entry], apply=True)["imported"] == 0


def test_prune_only_reviewed_orphans_keeps_metadata_and_inactive_accounts(db_session, profile_id):
    entry = PruneEntry(user_id=int(profile_id), expected_version=1)
    db_session.execute(text("INSERT INTO user_profiles(user_id,avatar_ready,avatar_data,additional_info) VALUES (:id,TRUE,:data,'{\"bio\":\"synthetic\"}')"),
                       {"id": profile_id, "data": image_bytes()})
    db_session.execute(text("UPDATE auth_user SET is_active=FALSE WHERE id=:id"), {"id": int(profile_id)})
    assert prune_avatars(db_session, [entry], apply=True)["cleared"] == 0
    db_session.execute(text("DELETE FROM auth_user WHERE id=:id"), {"id": int(profile_id)})
    assert prune_avatars(db_session, [entry])["eligible"] == 1
    assert prune_avatars(db_session, [entry])["cleared"] == 0
    assert prune_avatars(db_session, [entry.model_copy(update={"expected_version": 2})], apply=True)["cleared"] == 0
    assert prune_avatars(db_session, [entry], apply=True)["cleared"] == 1
    row = db_session.execute(text("SELECT avatar_data,version,additional_info FROM user_profiles WHERE user_id=:id"), {"id": profile_id}).one()
    assert row.avatar_data is None and row.version == 2 and row.additional_info == {"bio": "synthetic"}


def test_avatar_schema_upgrade_is_additive_repeatable_and_constrained(committed_engine):
    sql = Path("/profile-db/avatars.sql").read_text()
    with committed_engine.begin() as connection:
        connection.exec_driver_sql("CREATE TEMP TABLE user_profiles (profile_picture_url TEXT) ON COMMIT DROP")
        connection.exec_driver_sql("INSERT INTO user_profiles VALUES ('/static/synthetic.png')")
        connection.exec_driver_sql(sql)
        connection.exec_driver_sql(sql)
        assert tuple(connection.exec_driver_sql("SELECT * FROM user_profiles").one()) == ("/static/synthetic.png", None, False)
        for statement in ("UPDATE user_profiles SET avatar_ready=TRUE", "UPDATE user_profiles SET avatar_data=''::bytea",
                          "UPDATE user_profiles SET avatar_ready=TRUE,avatar_data=repeat('x',1048577)::bytea"):
            nested = connection.begin_nested()
            with pytest.raises(IntegrityError):
                connection.exec_driver_sql(statement)
            nested.rollback()
