import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "RagDocumentEmbeddingServices"))

from app.config.logging import configure_logging
from app.config.settings import get_settings
from app.infrastructure.database.connection import Database
from app.infrastructure.database.repositories.document_reader_pg import DocumentReaderPg
from app.infrastructure.database.repositories.vector_repository_pgvector import VectorRepositoryPgVector
from app.interfaces.workers.process_document_worker import process_document


def main() -> None:
    parser = argparse.ArgumentParser(description="Reindex one document or pending reindex documents.")
    parser.add_argument("--document-id")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    if not args.document_id and not args.all:
        parser.error("Use --document-id or --all")

    settings = get_settings()
    configure_logging(settings.log_level)
    database = Database(settings.database_url)
    database.open()
    try:
        with database.session() as session:
            vector_repository = VectorRepositoryPgVector(session)
            if args.document_id:
                vector_repository.delete_by_document_id(args.document_id)
                process_document(args.document_id, session, settings)
                return

            for document in DocumentReaderPg(session).get_pending_documents(args.limit):
                vector_repository.delete_by_document_id(document.document_id)
                process_document(document.document_id, session, settings)
    finally:
        database.close()


if __name__ == "__main__":
    main()
