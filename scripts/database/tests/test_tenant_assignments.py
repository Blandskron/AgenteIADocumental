"""Real logins/locks in a disposable database, never the application database."""
import os
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg


class Assignments(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = os.environ["PLAT_TEST_DATABASE"]
        if not cls.database.startswith("plat_assignments_"):
            raise RuntimeError("An explicitly named disposable database is required")
        cls.options = dict(host="postgres", dbname=cls.database, connect_timeout=5)
        cls.admin = psycopg.connect(**cls.options, user="postgres",
                                   password=os.environ["PLAT_TEST_ADMIN_PASSWORD"], autocommit=True)
        cls.migration = Path("/tmp/tenant-assignments.sql").read_text()
        cls.admin.execute("GRANT SELECT,INSERT,UPDATE,DELETE ON tenant_groups,tenant_memberships,tenant_user_groups TO auth_runtime")

    @classmethod
    def tearDownClass(cls):
        cls.admin.close()

    def apply(self):
        with self.admin.transaction():
            self.admin.execute(self.migration)

    def reset(self):
        self.admin.execute("TRUNCATE tenant_groups,tenant_memberships,tenant_user_groups CASCADE")

    def setUp(self):
        self.reset()
        self.apply()
        self.admin.execute("INSERT INTO tenants(tenant_id,name) VALUES('a','synthetic'),('b','synthetic') ON CONFLICT DO NOTHING")
        self.admin.execute("INSERT INTO tenant_groups(group_id,tenant_id,name) VALUES('ga','a','synthetic'),('gb','b','synthetic')")
        self.admin.execute("INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES('a','owner','USER')")

    def tearDown(self):
        self.reset()
        self.admin.execute("ALTER TABLE tenant_user_groups DROP CONSTRAINT IF EXISTS tenant_assignments_group_tenant_fk, DROP CONSTRAINT IF EXISTS tenant_assignments_membership_fk")
        self.apply()

    def runtime(self):
        connection = psycopg.connect(**self.options, user="auth_runtime", password=os.environ["POSTGRES_PASSWORD"])
        connection.execute("SET statement_timeout='5s'")
        self.assertEqual(connection.execute("SELECT current_user").fetchone()[0], "auth_runtime")
        return connection

    def test_login_rejects_cross_tenant_or_missing_membership(self):
        for group, owner in (("gb", "owner"), ("ga", "missing")):
            with self.runtime() as c:
                with self.assertRaises(psycopg.errors.ForeignKeyViolation):
                    c.execute("INSERT INTO tenant_user_groups(tenant_id,user_id,group_id) VALUES('a',%s,%s)", (owner, group))

    def test_repeat_and_cascade_preserve_other_memberships(self):
        self.apply()
        self.apply()
        with self.runtime() as c:
            c.execute("INSERT INTO tenant_user_groups(tenant_id,user_id,group_id) VALUES('a','owner','ga')")
            c.execute("DELETE FROM tenant_groups WHERE group_id='ga'")
            self.assertEqual(c.execute("SELECT count(*) FROM tenant_user_groups").fetchone()[0], 0)
            self.assertEqual(c.execute("SELECT count(*) FROM tenant_memberships").fetchone()[0], 1)

    def test_legacy_preflight_rolls_back_without_repair(self):
        self.admin.execute("ALTER TABLE tenant_user_groups DROP CONSTRAINT tenant_assignments_group_tenant_fk, DROP CONSTRAINT tenant_assignments_membership_fk")
        self.admin.execute("INSERT INTO tenant_user_groups(tenant_id,user_id,group_id) VALUES('a','orphan','gb')")
        before = self.admin.execute("SELECT * FROM tenant_user_groups").fetchall()
        with self.assertRaises(psycopg.Error) as error:
            self.apply()
        self.assertIn("preflight failed", error.exception.diag.message_primary)
        self.assertEqual(before, self.admin.execute("SELECT * FROM tenant_user_groups").fetchall())
        self.assertEqual(self.admin.execute("SELECT count(*) FROM pg_constraint WHERE conname LIKE 'tenant_assignments_%'").fetchone()[0], 0)

    def test_drift_is_not_overwritten(self):
        self.admin.execute("ALTER TABLE tenant_user_groups DROP CONSTRAINT tenant_assignments_group_tenant_fk")
        self.admin.execute("ALTER TABLE tenant_user_groups ADD CONSTRAINT tenant_assignments_group_tenant_fk CHECK(true)")
        with self.assertRaises(psycopg.Error) as error:
            self.apply()
        self.assertIn("schema drift", error.exception.diag.message_primary)
        self.assertEqual(self.admin.execute("SELECT contype FROM pg_constraint WHERE conname='tenant_assignments_group_tenant_fk'").fetchone()[0], "c")

    def race(self, parent, insert_first):
        delete = "DELETE FROM tenant_memberships WHERE tenant_id='a' AND user_id='owner'" if parent == "membership" else "DELETE FROM tenant_groups WHERE group_id='ga'"
        insert = "INSERT INTO tenant_user_groups(tenant_id,user_id,group_id) VALUES('a','owner','ga')"
        with self.runtime() as first, self.runtime() as second, ThreadPoolExecutor(1) as pool:
            first.execute(insert if insert_first else delete)
            pid = second.info.backend_pid

            def write():
                second.execute(delete if insert_first else insert)
                second.commit()

            future = pool.submit(write)
            deadline = time.monotonic() + 3
            waiting = False
            while time.monotonic() < deadline and not future.done():
                waiting = self.admin.execute("SELECT wait_event_type='Lock' FROM pg_stat_activity WHERE pid=%s", (pid,)).fetchone()[0]
                if waiting:
                    break
                time.sleep(0.02)
            try:
                self.assertTrue(waiting, "Expected a real PostgreSQL FK lock")
            finally:
                first.commit()
            if insert_first:
                future.result(timeout=5)
            else:
                with self.assertRaises(psycopg.errors.ForeignKeyViolation):
                    future.result(timeout=5)
                second.rollback()
        self.assertEqual(self.admin.execute("SELECT count(*) FROM tenant_user_groups").fetchone()[0], 0)

    def test_membership_delete_before_insert(self):
        self.race("membership", False)

    def test_membership_insert_before_delete(self):
        self.race("membership", True)

    def test_group_delete_before_insert(self):
        self.race("group", False)

    def test_group_insert_before_delete(self):
        self.race("group", True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
