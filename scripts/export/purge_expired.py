"""Explicit retention maintenance; dry-run by default, never touches legacy files."""
import argparse
import os

from sqlalchemy import create_engine, text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    engine = create_engine(os.environ["EXPORT_MIGRATION_DATABASE_URL"], hide_parameters=True)
    try:
        with engine.begin() as connection:
            count = connection.scalar(text("SELECT count(*) FROM document_exports WHERE pdf_data IS NOT NULL AND expires_at<=NOW()"))
            if args.apply:
                connection.execute(text("DELETE FROM document_exports WHERE pdf_data IS NOT NULL AND expires_at<=NOW()"))
            print("Expired database exports", "deleted:" if args.apply else "eligible (dry-run):", count)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
