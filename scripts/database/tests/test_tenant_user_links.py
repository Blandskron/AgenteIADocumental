"""Membership lifecycle using real Auth migrations and disposable PostgreSQL logins."""

import os
import sys
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import psycopg


class UserLinks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database = os.environ["PLAT_TEST_DATABASE"]
        if (
            not database.startswith("plat_identity_")
            or os.environ["POSTGRES_DB"] != database
        ):
            raise RuntimeError(
                "Disposable identity database required for SQL and Django"
            )
        cls.options = dict(host="postgres", dbname=database, connect_timeout=5)
        cls.admin = psycopg.connect(
            **cls.options,
            user="postgres",
            password=os.environ["PLAT_TEST_ADMIN_PASSWORD"],
            autocommit=True,
        )
        cls.body = Path("/tmp/tenant-user-links.sql").read_text()
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
        from django.contrib.auth.models import User

        self.admin.execute("TRUNCATE auth_user,tenants,documents CASCADE")
        self.apply()
        # ORM creation uses the real auth_runtime login and identity sequence.
        self.user = User.objects.create_user(username="synthetic-member")
        self.actor = User.objects.create_superuser(username="synthetic-operator")
        self.admin.execute(
            "INSERT INTO tenants(tenant_id,name) VALUES('a','synthetic'),('b','synthetic')"
        )
        self.admin.execute(
            "INSERT INTO tenant_groups(group_id,tenant_id,name) VALUES('group-a','a','synthetic')"
        )

    def tearDown(self):
        self.admin.execute("TRUNCATE auth_user,tenants,documents CASCADE")

    def runtime(self):
        connection = psycopg.connect(
            **self.options,
            user="auth_runtime",
            password=os.environ["POSTGRES_PASSWORD"],
        )
        connection.execute("SET statement_timeout='8s'")
        self.assertEqual(
            connection.execute("SELECT current_user").fetchone()[0], "auth_runtime"
        )
        return connection

    def membership(self, connection, tenant="a"):
        connection.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES(%s,%s,'USER')",
            (tenant, str(self.user.pk)),
        )

    def seed_config(self):
        with self.runtime() as c:
            self.membership(c)
            self.membership(c, "b")
            c.execute(
                "INSERT INTO tenant_user_groups(tenant_id,user_id,group_id) VALUES('a',%s,'group-a')",
                (str(self.user.pk),),
            )
        self.admin.execute(
            "INSERT INTO documents(document_id,tenant_id,owner_user_id,filename,storage_path,mime_type) VALUES('doc','a',%s,'synthetic','synthetic','text/plain')",
            (str(self.user.pk),),
        )

    def assert_documents_preserved(self):
        self.assertEqual(
            self.admin.execute(
                "SELECT tenant_id,owner_user_id,storage_path FROM documents"
            ).fetchone(),
            ("a", str(self.user.pk), "synthetic"),
        )

    def test_existing_user_and_text_contract(self):
        with self.runtime() as c:
            self.membership(c)
            self.assertEqual(
                c.execute(
                    "SELECT user_id,auth_user_id FROM tenant_memberships"
                ).fetchone(),
                (str(self.user.pk), self.user.pk),
            )
        from users.serializers import TenantMembershipSerializer

        self.assertNotIn("auth_user_id", TenantMembershipSerializer().fields)

    def test_noncanonical_and_unknown_ids_are_rejected(self):
        for value in (
            "0",
            "-1",
            "0" + str(self.user.pk),
            " " + str(self.user.pk),
            str(self.user.pk) + "\n",
            "１",
            "١",
            "unknown",
            "9" * 100,
        ):
            with self.subTest(value=value), self.runtime() as c:
                with self.assertRaises(psycopg.errors.CheckViolation) as error:
                    c.execute(
                        "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES('a',%s,'USER')",
                        (value,),
                    )
                self.assertEqual(
                    error.exception.diag.constraint_name,
                    "tenant_memberships_auth_user_check",
                )
                c.rollback()
        with self.runtime() as c:
            with self.assertRaises(psycopg.errors.ForeignKeyViolation) as error:
                c.execute(
                    "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES('a','2147483647','USER')"
                )
            self.assertEqual(
                error.exception.diag.constraint_name, "tenant_memberships_auth_user_fk"
            )
            c.rollback()

    def test_generated_identity_cannot_be_overridden(self):
        with self.runtime() as c:
            with self.assertRaises(psycopg.errors.GeneratedAlways):
                c.execute(
                    "INSERT INTO tenant_memberships(tenant_id,user_id,auth_user_id,role) VALUES('a','missing',%s,'USER')",
                    (self.user.pk,),
                )
            c.rollback()

    def test_sql_user_delete_removes_configuration_only(self):
        self.seed_config()
        with self.runtime() as c:
            c.execute("DELETE FROM auth_user WHERE id=%s", (self.user.pk,))
        for table in ("tenant_memberships", "tenant_user_groups"):
            self.assertEqual(
                self.admin.execute("SELECT count(*) FROM " + table).fetchone()[0], 0
            )
        self.assertEqual(
            self.admin.execute("SELECT count(*) FROM tenant_groups").fetchone()[0], 1
        )
        self.assert_documents_preserved()

    def test_disable_preserves_memberships_and_assignments(self):
        self.seed_config()
        with self.runtime() as c:
            c.execute(
                "UPDATE auth_user SET is_active=false WHERE id=%s", (self.user.pk,)
            )
        self.assertEqual(
            self.admin.execute("SELECT count(*) FROM tenant_memberships").fetchone()[0],
            2,
        )
        self.assertEqual(
            self.admin.execute("SELECT count(*) FROM tenant_user_groups").fetchone()[0],
            1,
        )
        self.assert_documents_preserved()

    def test_new_normal_account_does_not_reuse_deleted_identity(self):
        from django.contrib.auth.models import User

        self.seed_config()
        old_id = self.user.pk
        self.user.delete()
        replacement = User.objects.create_user(username="synthetic-replacement")
        self.assertNotEqual(replacement.pk, old_id)
        self.assertFalse(
            self.admin.execute(
                "SELECT EXISTS(SELECT 1 FROM tenant_memberships WHERE user_id=%s)",
                (str(replacement.pk),),
            ).fetchone()[0]
        )
        self.assertEqual(
            self.admin.execute("SELECT owner_user_id FROM documents").fetchone()[0],
            str(old_id),
        )

    def wait_for_lock(self, c, future):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not future.done():
            if self.admin.execute(
                "SELECT wait_event_type='Lock' FROM pg_stat_activity WHERE pid=%s",
                (c.info.backend_pid,),
            ).fetchone()[0]:
                return
            time.sleep(0.02)
        self.fail("Expected a real FK lock between two runtime logins")

    def race(self, insert_first, rollback=False):
        with (
            self.runtime() as first,
            self.runtime() as second,
            ThreadPoolExecutor(1) as pool,
        ):
            delete = "DELETE FROM auth_user WHERE id=%s"
            if insert_first:
                self.membership(first)
            else:
                first.execute(delete, (self.user.pk,))

            def write():
                if insert_first:
                    second.execute(delete, (self.user.pk,))
                else:
                    self.membership(second)
                second.commit()

            future = pool.submit(write)
            try:
                self.wait_for_lock(second, future)
            finally:
                first.rollback() if rollback else first.commit()
            if not insert_first and not rollback:
                with self.assertRaises(psycopg.errors.ForeignKeyViolation):
                    future.result(timeout=8)
                second.rollback()
            else:
                future.result(timeout=8)
        expected_members = int(not insert_first and rollback)
        self.assertEqual(
            self.admin.execute("SELECT count(*) FROM tenant_memberships").fetchone()[0],
            expected_members,
        )

    def test_user_delete_wins_against_membership_insert(self):
        self.race(False)

    def test_membership_insert_then_user_delete_cascades(self):
        self.race(True)

    def test_user_delete_rollback_allows_membership(self):
        self.race(False, rollback=True)

    def test_membership_rollback_allows_user_delete(self):
        self.race(True, rollback=True)

    def test_http_user_delete_cleans_config_and_invalidates_auth_session(self):
        from rest_framework.test import APIClient, APIRequestFactory, force_authenticate
        from rest_framework_simplejwt.tokens import RefreshToken
        from users.views import UserViewSet

        self.seed_config()
        access = str(RefreshToken.for_user(self.user).access_token)
        client = APIClient(HTTP_HOST="localhost")
        client.credentials(HTTP_AUTHORIZATION="Bearer " + access)
        self.assertEqual(client.get("/api/users/me/").status_code, 200)
        request = APIRequestFactory().delete(
            "/api/users/crud/" + str(self.user.pk) + "/"
        )
        force_authenticate(request, self.actor)
        response = UserViewSet.as_view({"delete": "destroy"}, basename="user")(
            request, pk=self.user.pk
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(client.get("/api/users/me/").status_code, 401)
        self.assertEqual(
            self.admin.execute("SELECT count(*) FROM tenant_memberships").fetchone()[0],
            0,
        )
        self.assertEqual(
            self.admin.execute("SELECT count(*) FROM tenant_user_groups").fetchone()[0],
            0,
        )
        self.assert_documents_preserved()

    def test_http_user_disappears_after_membership_validation(self):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from users.models import TenantMembership
        from users.serializers import TenantMembershipSerializer
        from users.views import TenantMembershipViewSet

        create = TenantMembershipSerializer.create

        def disappear(serializer, data):
            self.admin.execute("DELETE FROM auth_user WHERE id=%s", (self.user.pk,))
            return create(serializer, data)

        request = APIRequestFactory().post(
            "/api/users/tenant-memberships/",
            {"tenant": "a", "user_id": str(self.user.pk), "role": "USER"},
            format="json",
        )
        force_authenticate(request, self.actor)
        with patch.object(TenantMembershipSerializer, "create", disappear):
            response = TenantMembershipViewSet.as_view(
                {"post": "create"}, basename="tenant-membership"
            )(request)
        self.assertEqual(response.status_code, 409)
        self.assertNotIn("auth_user", str(response.data))
        self.assertEqual(TenantMembership.objects.count(), 0)

    def test_repeatable_without_auth_table_or_permission_changes(self):
        fingerprint = self.admin.execute(
            "SELECT relowner,relacl::text FROM pg_class WHERE oid='auth_user'::regclass"
        ).fetchone()
        self.apply()
        self.apply()
        self.assertEqual(
            self.admin.execute(
                "SELECT relowner,relacl::text FROM pg_class WHERE oid='auth_user'::regclass"
            ).fetchone(),
            fingerprint,
        )
        with self.runtime() as c:
            self.assertFalse(
                c.execute(
                    "SELECT has_table_privilege(current_user,'documents','DELETE')"
                ).fetchone()[0]
            )

    def test_first_activation_preserves_existing_valid_membership(self):
        with self.admin.transaction():
            self.admin.execute(
                "ALTER TABLE tenant_memberships DROP CONSTRAINT tenant_memberships_auth_user_fk, DROP CONSTRAINT tenant_memberships_auth_user_check"
            )
            self.admin.execute("DROP INDEX tenant_memberships_auth_user_idx")
            self.admin.execute(
                "ALTER TABLE tenant_memberships DROP COLUMN auth_user_id"
            )
            self.membership(self.admin)
            before = self.admin.execute(
                "SELECT user_id,membership_id,created_at FROM tenant_memberships"
            ).fetchone()
            self.apply()
            self.assertEqual(
                self.admin.execute(
                    "SELECT user_id,membership_id,created_at FROM tenant_memberships"
                ).fetchone(),
                before,
            )
            self.assertEqual(
                self.admin.execute(
                    "SELECT auth_user_id FROM tenant_memberships"
                ).fetchone()[0],
                self.user.pk,
            )
            raise psycopg.Rollback()

    def test_orphan_history_requires_review_without_repair(self):
        with self.admin.transaction():
            self.admin.execute(
                "ALTER TABLE tenant_memberships DROP CONSTRAINT tenant_memberships_auth_user_fk"
            )
            self.admin.execute(
                "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES('a','2147483647','USER')"
            )
            with self.assertRaises(psycopg.Error) as error:
                self.apply()
            self.assertIn("rows: 1", error.exception.diag.message_primary)
            self.assertNotIn("2147483647", error.exception.diag.message_primary)
            self.assertEqual(
                self.admin.execute(
                    "SELECT count(*) FROM tenant_memberships"
                ).fetchone()[0],
                1,
            )
            raise psycopg.Rollback()

    def test_noncanonical_history_is_not_normalized(self):
        with self.admin.transaction():
            self.admin.execute(
                "ALTER TABLE tenant_memberships DROP CONSTRAINT tenant_memberships_auth_user_check"
            )
            value = "0" + str(self.user.pk)
            self.admin.execute(
                "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES('a',%s,'USER')",
                (value,),
            )
            with self.assertRaises(psycopg.Error):
                self.apply()
            self.assertEqual(
                self.admin.execute("SELECT user_id FROM tenant_memberships").fetchone()[
                    0
                ],
                value,
            )
            raise psycopg.Rollback()

    def test_schema_drift_is_not_overwritten(self):
        mutations = (
            "ALTER TABLE tenant_memberships DISABLE TRIGGER ALL",
            "ALTER TABLE tenant_memberships DROP CONSTRAINT tenant_memberships_auth_user_fk; ALTER TABLE tenant_memberships ADD CONSTRAINT tenant_memberships_auth_user_fk FOREIGN KEY(auth_user_id) REFERENCES auth_user(id) ON DELETE RESTRICT",
            "ALTER TABLE tenant_memberships ALTER COLUMN auth_user_id DROP EXPRESSION",
            "CREATE INDEX redundant_identity ON tenant_memberships(user_id); DROP INDEX tenant_memberships_auth_user_idx; ALTER INDEX redundant_identity RENAME TO tenant_memberships_auth_user_idx",
            "ALTER TABLE tenant_memberships ADD CONSTRAINT extra_user_fk FOREIGN KEY(auth_user_id) REFERENCES auth_user(id) ON DELETE RESTRICT",
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.admin.transaction():
                self.admin.execute(mutation)
                with self.assertRaises(psycopg.Error) as error:
                    self.apply()
                self.assertIn("schema drift", error.exception.diag.message_primary)
                raise psycopg.Rollback()

    def test_late_failure_rolls_back_all_new_identity_objects(self):
        with self.admin.transaction():
            self.admin.execute(
                "ALTER TABLE tenant_memberships DROP CONSTRAINT tenant_memberships_auth_user_fk, DROP CONSTRAINT tenant_memberships_auth_user_check"
            )
            self.admin.execute("DROP INDEX tenant_memberships_auth_user_idx")
            self.admin.execute(
                "ALTER TABLE tenant_memberships DROP COLUMN auth_user_id"
            )
            # A qualified name collision is discovered after adding the column/FK.
            self.admin.execute(
                "CREATE TABLE public.tenant_memberships_auth_user_idx(marker int)"
            )
            with self.assertRaises(psycopg.Error):
                self.apply()
            self.assertEqual(
                self.admin.execute(
                    "SELECT count(*) FROM pg_attribute WHERE attrelid='tenant_memberships'::regclass AND attname='auth_user_id' AND NOT attisdropped"
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                self.admin.execute(
                    "SELECT count(*) FROM pg_constraint WHERE conrelid='tenant_memberships'::regclass AND conname='tenant_memberships_auth_user_fk'"
                ).fetchone()[0],
                0,
            )
            raise psycopg.Rollback()


if __name__ == "__main__":
    unittest.main(verbosity=2)
