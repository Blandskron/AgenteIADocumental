import argparse
import logging
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "RagDocumentEmbeddingServices"))

from app.config.logging import configure_logging
from app.config.settings import get_settings
from app.infrastructure.database.connection import Database
from app.infrastructure.database.repositories.document_reader_pg import DocumentReaderPg
from app.interfaces.workers.process_document_worker import process_document


def main() -> None:
    parser = argparse.ArgumentParser(description="Process pending documents in batches.")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    database = Database(settings.database_url)
    database.open()
    try:
        with database.session() as session:
            documents = DocumentReaderPg(session).get_pending_documents(args.limit)
            for document in documents:
                process_document(document.document_id, session, settings)
    finally:
        database.close()


if __name__ == "__main__":
    logging.getLogger(__name__).info("Starting pending document processor")
    main()
