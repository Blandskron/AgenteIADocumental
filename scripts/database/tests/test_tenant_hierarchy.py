"""Opt-in hierarchy migration; run only against a disposable plat_hierarchy_* DB."""

import os
import sys
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import psycopg


class Hierarchy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database = os.environ["PLAT_TEST_DATABASE"]
        if not database.startswith("plat_hierarchy_"):
            raise RuntimeError("Disposable hierarchy database required")
        cls.options = dict(host="postgres", dbname=database, connect_timeout=5)
        cls.admin = psycopg.connect(
            **cls.options,
            user="postgres",
            password=os.environ["PLAT_TEST_ADMIN_PASSWORD"],
            autocommit=True,
        )
        cls.body = Path("/tmp/tenant-hierarchy.sql").read_text()
        cls.admin.execute(
            "GRANT SELECT,INSERT,UPDATE,DELETE ON tenants,tenant_areas,tenant_memberships,tenant_groups,tenant_user_groups TO auth_runtime"
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
            self.admin.execute(self.body)

    def setUp(self):
        self.admin.execute("TRUNCATE tenants,documents CASCADE")
        self.apply()
        self.admin.execute(
            "INSERT INTO tenants(tenant_id,name) VALUES('a','synthetic'),('b','synthetic')"
        )
        self.admin.execute(
            "INSERT INTO tenant_areas(area_id,tenant_id,name,parent_area_id) VALUES('x','a','x',NULL),('y','a','y',NULL),('leaf','a','leaf','x'),('other','b','other',NULL)"
        )

    def tearDown(self):
        self.admin.execute("TRUNCATE tenants,documents CASCADE")

    def runtime(self, isolation="READ COMMITTED"):
        connection = psycopg.connect(
            **self.options,
            user="auth_runtime",
            password=os.environ["POSTGRES_PASSWORD"],
        )
        connection.execute("SET TRANSACTION ISOLATION LEVEL " + isolation)
        connection.execute("SET statement_timeout='8s'")
        self.assertEqual(
            connection.execute("SELECT current_user").fetchone()[0], "auth_runtime"
        )
        return connection

    def test_move_and_detach_remain_supported(self):
        with self.runtime() as c:
            c.execute("UPDATE tenant_areas SET parent_area_id='y' WHERE area_id='leaf'")
            c.execute(
                "UPDATE tenant_areas SET parent_area_id=NULL WHERE area_id='leaf'"
            )
            c.execute("UPDATE tenant_areas SET name='renamed' WHERE area_id='x'")
        self.assertEqual(
            self.admin.execute(
                "SELECT area_revision FROM tenants WHERE tenant_id='a'"
            ).fetchone()[0],
            2,
        )

    def test_self_and_descendant_cycles_roll_back(self):
        for parent in ("x", "leaf"):
            with self.subTest(parent=parent), self.runtime() as c:
                with self.assertRaises(psycopg.errors.CheckViolation) as error:
                    c.execute(
                        "UPDATE tenant_areas SET parent_area_id=%s WHERE area_id='x'",
                        (parent,),
                    )
                self.assertEqual(
                    error.exception.diag.constraint_name, "tenant_areas_acyclic"
                )
                c.rollback()
        self.assertIsNone(
            self.admin.execute(
                "SELECT parent_area_id FROM tenant_areas WHERE area_id='x'"
            ).fetchone()[0]
        )

    def test_multirow_cycle_is_atomic(self):
        with self.runtime() as c:
            with self.assertRaises(psycopg.errors.CheckViolation):
                c.execute(
                    "UPDATE tenant_areas SET parent_area_id=CASE area_id WHEN 'x' THEN 'y' ELSE 'x' END WHERE area_id IN ('x','y')"
                )
            c.rollback()
        self.assertEqual(
            self.admin.execute(
                "SELECT count(*) FROM tenant_areas WHERE area_id IN ('x','y') AND parent_area_id IS NULL"
            ).fetchone()[0],
            2,
        )

    def test_existing_same_tenant_parent_is_required(self):
        for parent in ("missing", "other"):
            with self.subTest(parent=parent), self.runtime() as c:
                with self.assertRaises(psycopg.errors.ForeignKeyViolation):
                    c.execute(
                        "INSERT INTO tenant_areas(area_id,tenant_id,name,parent_area_id) VALUES('new','a','new',%s)",
                        (parent,),
                    )
                c.rollback()

    def test_identity_cannot_be_reassigned(self):
        for mutation in ("tenant_id='b'", "area_id='replacement'"):
            with self.subTest(mutation=mutation), self.runtime() as c:
                with self.assertRaises(psycopg.errors.CheckViolation) as error:
                    c.execute(
                        "UPDATE tenant_areas SET " + mutation + " WHERE area_id='y'"
                    )
                self.assertEqual(
                    error.exception.diag.constraint_name,
                    "tenant_areas_identity_immutable",
                )
                c.rollback()

    def wait_for_lock(self, connection, future):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not future.done():
            if self.admin.execute(
                "SELECT wait_event_type='Lock' FROM pg_stat_activity WHERE pid=%s",
                (connection.info.backend_pid,),
            ).fetchone()[0]:
                return
            time.sleep(0.02)
        self.fail("Second real login did not wait for the tenant topology writer")

    def race(self, isolation, rollback=False, reverse=False):
        first_id, second_id = ("y", "x") if reverse else ("x", "y")
        with (
            self.runtime(isolation) as first,
            self.runtime(isolation) as second,
            ThreadPoolExecutor(1) as pool,
        ):
            # Both snapshots predate the first topology change, including at RR.
            first.execute("SELECT count(*) FROM tenant_areas")
            second.execute("SELECT count(*) FROM tenant_areas")
            first.execute(
                "UPDATE tenant_areas SET parent_area_id=%s WHERE area_id=%s",
                (second_id, first_id),
            )

            def write():
                second.execute(
                    "UPDATE tenant_areas SET parent_area_id=%s WHERE area_id=%s",
                    (first_id, second_id),
                )
                second.commit()

            future = pool.submit(write)
            try:
                self.wait_for_lock(second, future)
            finally:
                first.rollback() if rollback else first.commit()
            if rollback:
                future.result(timeout=8)
            else:
                expected = (
                    psycopg.errors.CheckViolation
                    if isolation == "READ COMMITTED"
                    else psycopg.errors.SerializationFailure
                )
                with self.assertRaises(expected):
                    future.result(timeout=8)
                second.rollback()
        self.assertEqual(
            self.admin.execute(
                "SELECT count(*) FROM tenant_areas WHERE area_id IN ('x','y') AND parent_area_id IS NOT NULL"
            ).fetchone()[0],
            1,
        )

    def test_read_committed_opposite_moves(self):
        self.race("READ COMMITTED")

    def test_read_committed_reverse_order(self):
        self.race("READ COMMITTED", reverse=True)

    def test_repeatable_read_opposite_moves(self):
        self.race("REPEATABLE READ")

    def test_serializable_opposite_moves(self):
        self.race("SERIALIZABLE")

    def test_rollback_unblocks_waiter_in_all_isolations(self):
        for isolation in ("READ COMMITTED", "REPEATABLE READ", "SERIALIZABLE"):
            with self.subTest(isolation=isolation):
                self.admin.execute(
                    "UPDATE tenant_areas SET parent_area_id=NULL WHERE area_id IN ('x','y')"
                )
                self.race(isolation, rollback=True)

    def test_different_tenants_do_not_share_topology_lock(self):
        with self.runtime() as first, self.runtime() as second:
            first.execute(
                "UPDATE tenant_areas SET parent_area_id='y' WHERE area_id='x'"
            )
            second.execute("SET lock_timeout='200ms'")
            second.execute(
                "INSERT INTO tenant_areas(area_id,tenant_id,name,parent_area_id) VALUES('other-child','b','new','other')"
            )

    def test_parent_and_tenant_deletion_preserve_document(self):
        self.admin.execute(
            "INSERT INTO documents(document_id,tenant_id,owner_user_id,owner_area_id,filename,storage_path,mime_type) VALUES('doc','a','historical','x','synthetic','synthetic','text/plain')"
        )
        with self.runtime() as c:
            c.execute("DELETE FROM tenant_areas WHERE area_id='x'")
        self.assertIsNone(
            self.admin.execute(
                "SELECT parent_area_id FROM tenant_areas WHERE area_id='leaf'"
            ).fetchone()[0]
        )
        with self.runtime() as c:
            c.execute("DELETE FROM tenants WHERE tenant_id='a'")
        self.assertEqual(
            self.admin.execute(
                "SELECT tenant_id,owner_area_id,owner_user_id,storage_path FROM documents"
            ).fetchone(),
            (None, None, "historical", "synthetic"),
        )

    def test_repeatable_without_new_function_privileges(self):
        self.apply()
        self.apply()
        with self.runtime() as c:
            self.assertFalse(
                c.execute(
                    "SELECT has_function_privilege(current_user,'public.guard_tenant_area_hierarchy()','EXECUTE')"
                ).fetchone()[0]
            )
            # The trigger can run as the invoker using its existing table grants.
            c.execute("UPDATE tenant_areas SET parent_area_id='y' WHERE area_id='x'")

    def test_corrupt_historical_cycle_is_not_repaired(self):
        with self.admin.transaction():
            self.admin.execute("SET LOCAL session_replication_role=replica")
            self.admin.execute(
                "UPDATE tenant_areas SET parent_area_id='leaf' WHERE area_id='x'"
            )
            self.admin.execute("SET LOCAL session_replication_role=origin")
            with self.assertRaises(psycopg.Error) as error:
                self.apply()
            self.assertIn("cycles: 2", error.exception.diag.message_primary)
            self.assertEqual(
                self.admin.execute(
                    "SELECT parent_area_id FROM tenant_areas WHERE area_id='x'"
                ).fetchone()[0],
                "leaf",
            )
            # Broken fixtures must never leave their synthetic transaction.
            raise psycopg.Rollback()

    def test_deep_history_requires_review_without_modification(self):
        with self.admin.transaction():
            self.admin.execute("SET LOCAL session_replication_role=replica")
            self.admin.execute(
                "INSERT INTO tenant_areas(area_id,tenant_id,name,parent_area_id) SELECT 'deep-'||n,'a','synthetic',CASE WHEN n<258 THEN 'deep-'||(n+1) END FROM generate_series(1,258) n"
            )
            self.admin.execute("SET LOCAL session_replication_role=origin")
            with self.assertRaises(psycopg.Error) as error:
                self.apply()
            self.assertIn("unresolved:", error.exception.diag.message_primary)
            self.assertEqual(
                self.admin.execute(
                    "SELECT count(*) FROM tenant_areas WHERE area_id LIKE 'deep-%'"
                ).fetchone()[0],
                258,
            )
            raise psycopg.Rollback()

    def test_late_activation_failure_rolls_back_new_column_and_function(self):
        with self.admin.transaction():
            self.admin.execute(
                "DROP TRIGGER tenant_areas_hierarchy_guard ON tenant_areas"
            )
            self.admin.execute("DROP FUNCTION public.guard_tenant_area_hierarchy()")
            self.admin.execute("ALTER TABLE tenants DROP COLUMN area_revision")
            # A conflicting trigger name is discovered after creating the new
            # column/function. Activation must leave this old schema intact.
            self.admin.execute(
                "CREATE TRIGGER tenant_areas_hierarchy_guard BEFORE UPDATE ON tenant_areas FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
            )
            with self.assertRaises(psycopg.Error):
                self.apply()
            self.assertIsNone(
                self.admin.execute(
                    "SELECT to_regprocedure('public.guard_tenant_area_hierarchy()')"
                ).fetchone()[0]
            )
            self.assertEqual(
                self.admin.execute(
                    "SELECT count(*) FROM pg_attribute WHERE attrelid='tenants'::regclass AND attname='area_revision' AND NOT attisdropped"
                ).fetchone()[0],
                0,
            )
            raise psycopg.Rollback()

    def test_schema_drift_is_not_overwritten(self):
        mutations = (
            "ALTER FUNCTION public.guard_tenant_area_hierarchy() SECURITY DEFINER",
            "ALTER FUNCTION public.guard_tenant_area_hierarchy() STABLE",
            "GRANT EXECUTE ON FUNCTION public.guard_tenant_area_hierarchy() TO PUBLIC",
            "ALTER TABLE public.tenant_areas DISABLE TRIGGER tenant_areas_hierarchy_guard",
            "ALTER TABLE public.tenants ALTER COLUMN area_revision SET DEFAULT 1",
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.admin.transaction():
                self.admin.execute(mutation)
                with self.assertRaises(psycopg.Error) as error:
                    self.apply()
                self.assertIn("schema drift", error.exception.diag.message_primary)
                raise psycopg.Rollback()

    def test_http_cycle_conflict_is_sanitized_and_connection_reusable(self):
        from django.contrib.auth.models import User
        from rest_framework.test import APIRequestFactory, force_authenticate
        from users.models import TenantArea
        from users.views import TenantAreaViewSet

        request = APIRequestFactory().patch(
            "/api/tenant-areas/x/", {"parent_area": "leaf"}, format="json"
        )
        force_authenticate(request, User(id=1, username="synthetic", is_superuser=True))
        response = TenantAreaViewSet.as_view(
            {"patch": "partial_update"}, basename="tenant-area"
        )(request, pk="x")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["detail"].code, "tenant_relation_conflict")
        self.assertNotIn("leaf", str(response.data))
        self.assertIsNone(TenantArea.objects.get(pk="x").parent_area_id)

    def test_error_classifier_does_not_hide_unknown_failures(self):
        from django.db import IntegrityError, OperationalError
        from users.relation_conflicts import is_relation_conflict

        for state, constraint, error_type, expected in (
            ("23503", "tenant_areas_tenant_id_fkey", IntegrityError, True),
            ("23514", "tenant_areas_acyclic", IntegrityError, True),
            ("23514", "unrelated_check", IntegrityError, False),
            ("23505", "tenant_areas_acyclic", IntegrityError, False),
            ("40001", None, OperationalError, True),
            ("40P01", None, OperationalError, True),
            ("55P03", None, OperationalError, True),
            ("08006", None, OperationalError, False),
        ):
            with self.subTest(state=state, constraint=constraint):
                cause = Exception("synthetic private database message")
                cause.sqlstate = state
                cause.diag = SimpleNamespace(constraint_name=constraint)
                error = error_type("synthetic private database message")
                error.__cause__ = cause
                self.assertEqual(is_relation_conflict(error), expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
