"""CI-only cleanup of a marked synthetic development probe, not a storage reconciler."""
import os
import re
import sys

from sqlalchemy import text

def main():
    sys.path.insert(0, "/app")
    from app.infrastructure.database.connection import Database

    marker = os.environ.get("EXPORT_PROBE_MARKER", "")
    if os.environ.get("EXPORT_PROBE_ALLOW_CLEANUP") != "synthetic-ci" or re.fullmatch(r"[0-9a-f]{32}", marker) is None:
        raise RuntimeError("Explicit local synthetic marker is required.")
    title = "EXPORT003-" + marker
    database = Database(os.environ["EXPORT_TEST_DATABASE_URL"])
    try:
        with database.session() as session:
            assert session.scalar(text("SELECT count(*) FROM auth_user WHERE username LIKE :name"), {"name": "export003-" + marker + "-%"}) == 0
            session.execute(text("DELETE FROM document_exports WHERE metadata->>'export_probe'=:marker"), {"marker": marker})
            session.execute(text("DELETE FROM conversations WHERE title=:title"), {"title": title})
            session.commit()
            assert session.scalar(text("SELECT count(*) FROM document_exports WHERE metadata->>'export_probe'=:marker"), {"marker": marker}) == 0
            assert session.scalar(text("SELECT count(*) FROM conversations WHERE title=:title"), {"title": title}) == 0
        print("Export HTTP: tagged SQL rows, conversation references and synthetic PDFs cleaned")
    finally:
        database.close()


if __name__ == "__main__":
    main()
