import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.domain.entities import ChatPdfExport
from app.infrastructure.pdf.chat_pdf_renderer import ChatPdfRenderer
from app.infrastructure.pdf.legacy import read_legacy

pytestmark = pytest.mark.postgres


def command(name, settings, *args):
    path = Path("/export-checks") / name
    if not path.exists():
        path = Path(__file__).parents[3] / "scripts/export" / name
    env = {**os.environ, "EXPORT_MIGRATION_DATABASE_URL": settings.database_url, "PYTHONPATH": os.pathsep.join(sys.path)}
    return subprocess.run([sys.executable, str(path), *map(str, args)], env=env, capture_output=True, timeout=15)


def seed(engine, owner, path):
    identifier = uuid4().hex
    content = ChatPdfRenderer().render(ChatPdfExport("Legado sintético", "", "Fuente preservada"))
    path.write_bytes(content)
    with engine.begin() as connection:
        connection.execute(text("""INSERT INTO document_exports (export_id,owner_user_id,source_type,title,filename,storage_path,file_size_bytes)
            VALUES (:id,:owner,'chat_message','Legacy','legacy.pdf',:path,:size)"""),
                           {"id": identifier, "owner": owner, "path": str(path), "size": len(content)})
    return identifier, content


def test_manifest_dry_run_apply_replay_and_source_preservation(committed_engine, owner, settings, tmp_path):
    identifier, content = seed(committed_engine, owner, tmp_path / "legacy.pdf")
    manifest = tmp_path / "inventory.json"
    args = ["--base", tmp_path, "--manifest", manifest]
    assert command("migrate_legacy.py", settings, *args).returncode == 0
    entries = json.loads(manifest.read_text())
    assert entries == [{"export_id": identifier, "owner_user_id": owner, "sha256": sha256(content).hexdigest(), "byte_count": len(content), "state": "ready"}]
    with committed_engine.connect() as connection:
        assert connection.scalar(text("SELECT pdf_data FROM document_exports WHERE export_id=:id"), {"id": identifier}) is None
    for _ in range(2):
        result = command("migrate_legacy.py", settings, *args, "--apply")
        assert result.returncode == 0, result.stderr.decode()[-500:]
    assert (tmp_path / "legacy.pdf").read_bytes() == content
    with committed_engine.connect() as connection:
        assert connection.scalar(text("SELECT pdf_data FROM document_exports WHERE export_id=:id"), {"id": identifier}) == content


def test_changed_file_or_manifest_never_overwrites_rows(committed_engine, owner, settings, tmp_path):
    identifier, content = seed(committed_engine, owner, tmp_path / "legacy.pdf")
    manifest = tmp_path / "review.json"
    args = ["--base", tmp_path, "--manifest", manifest]
    assert command("migrate_legacy.py", settings, *args).returncode == 0
    (tmp_path / "legacy.pdf").write_bytes(content + b"changed")
    assert command("migrate_legacy.py", settings, *args, "--apply").returncode != 0
    with committed_engine.connect() as connection:
        assert connection.scalar(text("SELECT pdf_data FROM document_exports WHERE export_id=:id"), {"id": identifier}) is None
    assert (tmp_path / "legacy.pdf").read_bytes() == content + b"changed"


@pytest.mark.parametrize("kind", ["outside", "link", "ancestor", "fifo", "missing", "oversize"])
def test_descriptor_rejects_unsafe_legacy_resources(tmp_path, kind):
    base = tmp_path / "base"
    base.mkdir()
    path = base / "candidate.pdf"
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"%PDF-synthetic")
    if kind == "outside":
        path = outside
    elif kind == "link":
        path.symlink_to(outside)
    elif kind == "ancestor":
        link = tmp_path / "linked"
        link.symlink_to(base, target_is_directory=True)
        base, path = link, link / "candidate.pdf"
    elif kind == "fifo":
        os.mkfifo(path)
    elif kind == "oversize":
        path.write_bytes(b"%PDF-" + b"x" * 1_048_576)
    with pytest.raises((ValueError, OSError)):
        read_legacy(base, path)
    assert outside.read_bytes() == b"%PDF-synthetic"


def test_retention_is_explicit_and_legacy_sources_are_preserved(committed_engine, owner, settings, tmp_path):
    identifier, content = seed(committed_engine, owner, tmp_path / "legacy.pdf")
    second, _ = seed(committed_engine, owner, tmp_path / "second.pdf")
    with committed_engine.begin() as connection:
        connection.execute(text("UPDATE document_exports SET pdf_data=:data,pdf_sha256=:digest,expires_at=:expiry WHERE export_id=:id"),
                           {"id": identifier, "data": content, "digest": sha256(content).hexdigest(), "expiry": datetime.now(UTC) - timedelta(days=1)})
    assert command("purge_expired.py", settings).returncode == 0
    with committed_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM document_exports WHERE export_id=:id"), {"id": identifier}) == 1
    assert command("purge_expired.py", settings, "--apply").returncode == 0
    with committed_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM document_exports WHERE export_id=:id"), {"id": identifier}) == 0
        assert connection.scalar(text("SELECT count(*) FROM document_exports WHERE export_id=:id"), {"id": second}) == 1
    assert (tmp_path / "legacy.pdf").read_bytes() == content


def test_storage_schema_repeats_and_rejects_partial_wrong_types(db_session):
    from sqlalchemy.exc import DBAPIError
    path = Path("/export-db/pdf_storage.sql")
    sql = path.read_text()
    for _ in range(2):
        db_session.connection().exec_driver_sql(sql)
    transaction = db_session.begin_nested()
    db_session.execute(text("ALTER TABLE document_exports ALTER COLUMN expires_at TYPE DATE"))
    with pytest.raises(DBAPIError, match="explicit repair required"):
        db_session.connection().exec_driver_sql(sql)
    transaction.rollback()
    assert db_session.scalar(text("SELECT format_type(atttypid,atttypmod) FROM pg_attribute WHERE attrelid='document_exports'::regclass AND attname='expires_at'")) == "timestamp with time zone"
