"""Exercise the real embedding writer and compensation against activated FKs."""

import os
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import psycopg
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.application.documents.use_cases.upload_document import UploadDocument
from app.infrastructure.database.repositories.document_writer_pg import DocumentWriterPg
from app.shared.errors import ConflictError, DocumentRelationConflict


class EmbeddingRelations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database = os.environ["PLAT_TEST_DATABASE"]
        if not database.startswith("plat_relations_"):
            raise RuntimeError("Disposable database required")
        cls.admin = psycopg.connect(
            host="postgres",
            dbname=database,
            user="postgres",
            password=os.environ["PLAT_TEST_ADMIN_PASSWORD"],
            autocommit=True,
        )
        cls.engine = create_engine(
            URL.create(
                "postgresql+psycopg",
                username="embedding_runtime",
                password=os.environ["PGPASSWORD"],
                host="postgres",
                database=database,
            ),
            hide_parameters=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        cls.admin.close()

    def setUp(self):
        self.admin.execute("TRUNCATE tenants,documents CASCADE")
        self.admin.execute(
            "INSERT INTO tenants(tenant_id,name) VALUES('a','synthetic'),('b','synthetic')"
        )
        self.admin.execute(
            "INSERT INTO tenant_areas(area_id,tenant_id,name) VALUES('area','a','synthetic')"
        )

    def tearDown(self):
        self.admin.execute("TRUNCATE tenants,documents CASCADE")

    def test_commit_conflict_rolls_back_storage_and_session_recovers(self):
        removed = []
        storage = SimpleNamespace(
            save=lambda *args: ("synthetic-storage", 1), remove=removed.append
        )
        with Session(self.engine) as session:
            writer = DocumentWriterPg(session)
            upload = UploadDocument(
                writer,
                storage,
                SimpleNamespace(
                    execute=lambda *args: self.fail("No processing after conflict")
                ),
            )
            for tenant in (None, "b"):
                with self.assertRaises(ConflictError) as e:
                    upload.execute(
                        "synthetic.txt",
                        "text/plain",
                        None,
                        {
                            "tenant_id": tenant,
                            "owner_area_id": "area",
                            "owner_user_id": "owner",
                        },
                    )
                self.assertNotIn("Key (", str(e.exception))
                self.assertIsInstance(e.exception, DocumentRelationConflict)
                self.assertNotIn("documents_area_tenant_fk", str(e.exception))
                self.assertEqual(
                    session.execute(text("SELECT count(*) FROM documents")).scalar(), 0
                )
            result = writer.create(
                "synthetic.txt",
                "synthetic-storage",
                "text/plain",
                {"tenant_id": "a", "owner_area_id": "area", "owner_user_id": "owner"},
            )
            self.assertEqual(result.tenant_id, "a")
        self.assertEqual(removed, ["synthetic-storage", "synthetic-storage"])

    def race(self, parent, insert_first):
        insert = "INSERT INTO documents(tenant_id,owner_area_id,owner_user_id,filename,storage_path,mime_type) VALUES('a','area','owner','synthetic.txt','synthetic','text/plain')"
        delete = (
            "DELETE FROM tenants WHERE tenant_id='a'"
            if parent == "tenant"
            else "DELETE FROM tenant_areas WHERE area_id='area'"
        )
        database = os.environ["PLAT_TEST_DATABASE"]
        writer = psycopg.connect(
            host="postgres",
            dbname=database,
            user="embedding_runtime",
            password=os.environ["PGPASSWORD"],
        )
        deleter = psycopg.connect(
            host="postgres",
            dbname=database,
            user="auth_runtime",
            password=os.environ["PLAT_TEST_AUTH_PASSWORD"],
        )
        first, second = (writer, deleter) if insert_first else (deleter, writer)
        with first, second, ThreadPoolExecutor(1) as pool:
            for c in (first, second):
                c.execute("SET statement_timeout='5s'")
            first.execute(insert if insert_first else delete)

            def write():
                second.execute(delete if insert_first else insert)
                second.commit()

            future = pool.submit(write)
            deadline, waiting = time.monotonic() + 3, False
            while time.monotonic() < deadline and not future.done():
                waiting = self.admin.execute(
                    "SELECT wait_event_type='Lock' FROM pg_stat_activity WHERE pid=%s",
                    (second.info.backend_pid,),
                ).fetchone()[0]
                if waiting:
                    break
                time.sleep(0.02)
            try:
                self.assertTrue(waiting)
            finally:
                first.commit()
            if insert_first:
                future.result(timeout=5)
            else:
                with self.assertRaises(psycopg.errors.ForeignKeyViolation):
                    future.result(timeout=5)
                second.rollback()
        rows = self.admin.execute(
            "SELECT tenant_id,owner_area_id,owner_user_id,storage_path FROM documents"
        ).fetchall()
        self.assertEqual(
            rows,
            [(None if parent == "tenant" else "a", None, "owner", "synthetic")]
            if insert_first
            else [],
        )

    def test_area_delete_before_upload(self):
        self.race("area", False)

    def test_area_upload_before_delete(self):
        self.race("area", True)

    def test_tenant_delete_before_upload(self):
        self.race("tenant", False)

    def test_tenant_upload_before_delete(self):
        self.race("tenant", True)

    def test_global_and_tenant_without_area_still_work(self):
        with Session(self.engine) as session:
            writer = DocumentWriterPg(session)
            for tenant in (None, "a"):
                result = writer.create(
                    "synthetic.txt",
                    "synthetic-storage",
                    "text/plain",
                    {"tenant_id": tenant, "owner_user_id": "owner"},
                )
                self.assertEqual(result.tenant_id, tenant)


if __name__ == "__main__":
    unittest.main(verbosity=2)
