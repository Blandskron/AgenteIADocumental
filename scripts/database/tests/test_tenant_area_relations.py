"""Migration, real auth_runtime logins and HTTP conflicts in a disposable DB."""

import os
import sys
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import psycopg


class AreaRelations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = os.environ["PLAT_TEST_DATABASE"]
        if not cls.database.startswith("plat_relations_"):
            raise RuntimeError("Disposable database required")
        cls.options = dict(host="postgres", dbname=cls.database, connect_timeout=5)
        cls.admin = psycopg.connect(
            **cls.options,
            user="postgres",
            password=os.environ["PLAT_TEST_ADMIN_PASSWORD"],
            autocommit=True,
        )
        cls.assignment_sql = Path("/tmp/tenant-assignments.sql").read_text()
        cls.area_sql = Path("/tmp/tenant-areas.sql").read_text()
        cls.admin.execute(
            "GRANT SELECT,INSERT,UPDATE,DELETE ON tenants,tenant_areas,tenant_memberships,tenant_groups,tenant_group_permissions,tenant_user_groups TO auth_runtime"
        )
        sys.path.insert(0, "/app")
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
        import django

        django.setup()

    @classmethod
    def tearDownClass(cls):
        from django.db import connections

        connections.close_all()
        cls.admin.close()

    def apply(self):
        with self.admin.transaction():
            self.admin.execute(self.assignment_sql)
            self.admin.execute(self.area_sql)

    def setUp(self):
        self.admin.execute("TRUNCATE tenants,documents CASCADE")
        self.apply()
        self.admin.execute(
            "INSERT INTO tenants(tenant_id,name) VALUES('a','synthetic'),('b','synthetic')"
        )
        self.admin.execute(
            "INSERT INTO tenant_areas(area_id,tenant_id,name,parent_area_id) VALUES('root','a','root',NULL),('child','a','child','root'),('foreign','b','foreign',NULL)"
        )
        self.admin.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role,area_id) VALUES('a','owner','USER','root')"
        )
        self.admin.execute(
            "INSERT INTO documents(document_id,tenant_id,owner_user_id,owner_area_id,filename,storage_path,mime_type) VALUES('document','a','owner','root','synthetic.txt','synthetic','text/plain')"
        )

    def tearDown(self):
        self.admin.execute("TRUNCATE tenants,documents CASCADE")
        self.admin.execute(
            "ALTER TABLE tenant_areas DROP CONSTRAINT IF EXISTS tenant_areas_parent_tenant_fk"
        )
        self.apply()

    def runtime(self):
        c = psycopg.connect(
            **self.options,
            user="auth_runtime",
            password=os.environ["POSTGRES_PASSWORD"],
        )
        c.execute("SET statement_timeout='5s'")
        self.assertEqual(c.execute("SELECT current_user").fetchone()[0], "auth_runtime")
        return c

    def test_rejects_foreign_parent_and_membership(self):
        for sql in (
            "UPDATE tenant_areas SET parent_area_id='foreign' WHERE area_id='child'",
            "UPDATE tenant_memberships SET area_id='foreign'",
        ):
            with (
                self.runtime() as c,
                self.assertRaises(psycopg.errors.ForeignKeyViolation),
            ):
                c.execute(sql)

    def test_document_optional_area_and_global_document(self):
        with self.admin.transaction():
            self.admin.execute(
                "INSERT INTO documents(document_id,tenant_id,filename,storage_path,mime_type) VALUES('no-area','a','x','synthetic','text/plain'),('global',NULL,'x','synthetic','text/plain')"
            )
        for tenant, area in (("b", "root"), (None, "root")):
            with self.assertRaises(psycopg.errors.ForeignKeyViolation):
                with self.admin.transaction():
                    self.admin.execute(
                        "UPDATE documents SET tenant_id=%s,owner_area_id=%s WHERE document_id='document'",
                        (tenant, area),
                    )
        self.assertEqual(
            self.admin.execute(
                "SELECT tenant_id,owner_area_id FROM documents WHERE document_id='document'"
            ).fetchone(),
            ("a", "root"),
        )

    def test_area_delete_nulls_only_optional_references(self):
        with self.runtime() as c:
            c.execute("DELETE FROM tenant_areas WHERE area_id='root'")
        self.assertEqual(
            self.admin.execute(
                "SELECT tenant_id,parent_area_id FROM tenant_areas WHERE area_id='child'"
            ).fetchone(),
            ("a", None),
        )
        self.assertEqual(
            self.admin.execute(
                "SELECT tenant_id,area_id FROM tenant_memberships"
            ).fetchone(),
            ("a", None),
        )
        self.assertEqual(
            self.admin.execute(
                "SELECT tenant_id,owner_area_id,owner_user_id,storage_path FROM documents"
            ).fetchone(),
            ("a", None, "owner", "synthetic"),
        )

    def test_tenant_delete_preserves_document_without_new_runtime_grants(self):
        with self.runtime() as c:
            self.assertFalse(
                c.execute(
                    "SELECT has_any_column_privilege(current_user,'documents','SELECT')"
                ).fetchone()[0]
            )
            c.execute("DELETE FROM tenants WHERE tenant_id='a'")
        self.assertEqual(
            self.admin.execute(
                "SELECT tenant_id,owner_area_id,owner_user_id,storage_path FROM documents"
            ).fetchone(),
            (None, None, "owner", "synthetic"),
        )

    def test_repeat_preserves_user_fields_and_generated_column_is_not_writable(self):
        before = self.admin.execute(
            "SELECT metadata,updated_at FROM documents"
        ).fetchall()
        self.apply()
        self.apply()
        self.assertEqual(
            before,
            self.admin.execute("SELECT metadata,updated_at FROM documents").fetchall(),
        )
        with self.assertRaises(psycopg.errors.GeneratedAlways):
            self.admin.execute("UPDATE documents SET owner_area_tenant_id='forged'")

    def test_legacy_rejection_and_drift_do_not_repair(self):
        self.admin.execute(
            "ALTER TABLE tenant_areas DROP CONSTRAINT tenant_areas_parent_tenant_fk"
        )
        self.admin.execute(
            "ALTER TABLE tenant_user_groups DROP CONSTRAINT tenant_assignments_group_tenant_fk, DROP CONSTRAINT tenant_assignments_membership_fk"
        )
        self.admin.execute(
            "UPDATE tenant_areas SET parent_area_id='foreign' WHERE area_id='child'"
        )
        with self.assertRaises(psycopg.Error) as e:
            self.apply()
        self.assertIn("preflight failed", e.exception.diag.message_primary)
        self.assertEqual(
            self.admin.execute(
                "SELECT count(*) FROM pg_constraint WHERE conname LIKE 'tenant_assignments_%'"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            self.admin.execute(
                "SELECT parent_area_id FROM tenant_areas WHERE area_id='child'"
            ).fetchone()[0],
            "foreign",
        )
        self.admin.execute(
            "UPDATE tenant_areas SET parent_area_id=NULL WHERE area_id='child'"
        )
        self.admin.execute(
            "ALTER TABLE tenant_areas ADD CONSTRAINT tenant_areas_parent_tenant_fk CHECK(true)"
        )
        with self.assertRaises(psycopg.Error) as e:
            self.apply()
        self.assertIn("schema drift", e.exception.diag.message_primary)

    def race(self, insert_first):
        insert = "INSERT INTO tenant_areas(area_id,tenant_id,name,parent_area_id) VALUES('new','a','new','root')"
        delete = "DELETE FROM tenant_areas WHERE area_id='root'"
        with (
            self.runtime() as first,
            self.runtime() as second,
            ThreadPoolExecutor(1) as pool,
        ):
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
        self.assertFalse(
            self.admin.execute(
                "SELECT EXISTS(SELECT 1 FROM tenant_areas WHERE parent_area_id='root')"
            ).fetchone()[0]
        )

    def test_parent_delete_before_insert(self):
        self.race(False)

    def test_parent_insert_before_delete(self):
        self.race(True)

    def test_unexpected_cascade_is_rejected_without_changing_it(self):
        for table, column, original in (
            ("documents", "owner_area_id", "documents_owner_area_id_fkey"),
            ("tenant_areas", "parent_area_id", "tenant_areas_parent_area_id_fkey"),
            ("tenant_memberships", "area_id", "tenant_memberships_area_id_fkey"),
        ):
            with self.subTest(table=table):
                self.admin.execute("BEGIN")
                try:
                    from psycopg import sql

                    self.admin.execute(
                        sql.SQL("ALTER TABLE {} DROP CONSTRAINT {}").format(
                            sql.Identifier(table), sql.Identifier(original)
                        )
                    )
                    self.admin.execute(
                        sql.SQL(
                            "ALTER TABLE {} ADD CONSTRAINT unexpected_cascade FOREIGN KEY ({}) REFERENCES tenant_areas(area_id) ON DELETE CASCADE"
                        ).format(sql.Identifier(table), sql.Identifier(column))
                    )
                    with self.assertRaises(psycopg.Error) as error:
                        self.apply()
                    self.assertIn(
                        "lifecycle foreign key", error.exception.diag.message_primary
                    )
                    self.assertEqual(
                        self.admin.execute(
                            "SELECT confdeltype FROM pg_constraint WHERE conname='unexpected_cascade'"
                        ).fetchone()[0],
                        "c",
                    )
                finally:
                    self.admin.execute("ROLLBACK")

    def test_generated_column_drift_is_not_repaired(self):
        self.admin.execute("BEGIN")
        try:
            self.admin.execute(
                "ALTER TABLE documents DROP CONSTRAINT documents_area_tenant_fk"
            )
            self.admin.execute(
                "ALTER TABLE documents ALTER COLUMN owner_area_tenant_id DROP EXPRESSION"
            )
            with self.assertRaises(psycopg.Error):
                self.apply()
            self.assertEqual(
                self.admin.execute(
                    "SELECT attgenerated FROM pg_attribute WHERE attrelid='documents'::regclass AND attname='owner_area_tenant_id'"
                ).fetchone()[0],
                "",
            )
        finally:
            self.admin.execute("ROLLBACK")

    def test_http_tenant_delete_preserves_document(self):
        from django.contrib.auth.models import User
        from rest_framework.test import APIRequestFactory, force_authenticate
        from users.views import TenantViewSet

        request = APIRequestFactory().delete("/api/tenants/a/")
        force_authenticate(request, User(id=1, username="synthetic", is_superuser=True))
        response = TenantViewSet.as_view({"delete": "destroy"}, basename="tenant")(
            request, pk="a"
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(
            self.admin.execute(
                "SELECT tenant_id,owner_area_id,owner_user_id,storage_path FROM documents"
            ).fetchone(),
            (None, None, "owner", "synthetic"),
        )

    def test_http_conflict_after_parent_disappears(self):
        from django.contrib.auth.models import User
        from rest_framework.test import APIRequestFactory, force_authenticate
        from users.models import TenantArea
        from users.serializers import TenantAreaSerializer
        from users.views import TenantAreaViewSet

        create = TenantAreaSerializer.create

        def disappear(serializer, data):
            self.admin.execute("DELETE FROM tenant_areas WHERE area_id='root'")
            return create(serializer, data)

        request = APIRequestFactory().post(
            "/api/tenant-areas/",
            {"tenant": "a", "name": "new", "parent_area": "root"},
            format="json",
        )
        force_authenticate(request, User(id=1, username="synthetic", is_superuser=True))
        with patch.object(TenantAreaSerializer, "create", disappear):
            response = TenantAreaViewSet.as_view(
                {"post": "create"}, basename="tenant-area"
            )(request)
        self.assertEqual(response.status_code, 409)
        self.assertNotIn("root", str(response.data))
        self.assertFalse(TenantArea.objects.filter(name="new").exists())
        # The failed transaction/connection must be reusable on the next request.
        self.assertEqual(TenantArea.objects.filter(tenant_id="b").count(), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
