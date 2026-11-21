import json

from django.contrib.auth.models import Permission, User
from django.db import connection
from django.test import TestCase

from users.models import (
    Tenant,
    TenantArea,
    TenantGroup,
    TenantGroupPermission,
    TenantMembership,
    TenantUserGroup,
)
from users.secrets_cipher import SecretDecryptionError, SecretsCipher
from users.serializers import serialize_user_profile
from users.views import user_can_manage_ai_settings


STRONG_KEY_1 = "synthetic-master-key-alpha-0123456789abcdef"
STRONG_KEY_2 = "synthetic-master-key-beta-fedcba9876543210!"


class SecretsCipherTests(TestCase):
    def test_encrypt_decrypt_roundtrip_and_fingerprint(self):
        cipher = SecretsCipher(STRONG_KEY_1, key_id="v1")
        token = cipher.encrypt("synthetic-groq-api-key-value")
        self.assertTrue(token.startswith("secrets1.v1."))
        self.assertEqual(cipher.decrypt(token), "synthetic-groq-api-key-value")
        self.assertIsNone(cipher.encrypt(None))
        self.assertIsNone(cipher.decrypt(None))

        fp = SecretsCipher.fingerprint("synthetic-groq-api-key-value")
        self.assertEqual(len(fp), 4)
        self.assertTrue(all(ch in "0123456789abcdef" for ch in fp))
        self.assertNotIn("value", fp)

    def test_key_rotation_decrypts_previous_and_encrypts_with_active(self):
        first = SecretsCipher(STRONG_KEY_1, key_id="v1")
        old_ciphertext = first.encrypt("synthetic-provider-secret")

        rotated = SecretsCipher(STRONG_KEY_2, key_id="v2", previous={"v1": STRONG_KEY_1})
        self.assertEqual(rotated.decrypt(old_ciphertext), "synthetic-provider-secret")

        new_ciphertext = rotated.encrypt("synthetic-provider-secret")
        self.assertTrue(new_ciphertext.startswith("secrets1.v2."))
        self.assertEqual(SecretsCipher(STRONG_KEY_2, key_id="v2").decrypt(new_ciphertext), "synthetic-provider-secret")

        with self.assertRaises(SecretDecryptionError):
            SecretsCipher(STRONG_KEY_2, key_id="v2").decrypt(old_ciphertext)

    def test_rejects_weak_example_or_invalid_keys(self):
        weak_values = [
            "",
            "short-key",
            "a" * 40,
            "change-me-with-a-long-random-secret-value-0001",
            "local-dev-secret-key-0123456789abcdef012345",
            "example-secret-key-0123456789abcdef01234567",
            "django-insecure-0123456789abcdef0123456789ab",
        ]
        for secret in weak_values:
            with self.subTest(secret=secret), self.assertRaises(ValueError):
                SecretsCipher(secret, key_id="v1")

        with self.assertRaises(ValueError):
            SecretsCipher(STRONG_KEY_1, key_id="bad id!")

        with self.assertRaises(ValueError):
            SecretsCipher(STRONG_KEY_1, key_id="v1", previous={"v1": STRONG_KEY_2})

        with self.assertRaises(ValueError):
            SecretsCipher(
                STRONG_KEY_1,
                key_id="v5",
                previous={
                    "v1": STRONG_KEY_2,
                    "v2": STRONG_KEY_2 + "2",
                    "v3": STRONG_KEY_2 + "3",
                    "v4": STRONG_KEY_2 + "4",
                },
            )

    def test_rejects_tampered_or_wrong_prefix_ciphertext(self):
        cipher = SecretsCipher(STRONG_KEY_1, key_id="v1")
        with self.assertRaises(SecretDecryptionError):
            cipher.decrypt("drive1.v1.invalid-prefix")
        with self.assertRaises(SecretDecryptionError):
            cipher.decrypt("secrets1.v1.not-a-valid-fernet-token")

    def test_from_environ_loads_and_returns_none_when_unset(self):
        self.assertIsNone(SecretsCipher.from_environ({}))
        cipher = SecretsCipher.from_environ({
            "SECRETS_ENCRYPTION_KEY": STRONG_KEY_2,
            "SECRETS_KEY_ID": "v2",
            "SECRETS_PREVIOUS_KEYS": json.dumps({"v1": STRONG_KEY_1}),
        })
        self.assertIsNotNone(cipher)
        self.assertEqual(cipher.key_id, "v2")


class ManageAISettingsPermissionTests(TestCase):
    tenant_models = (Tenant, TenantArea, TenantMembership, TenantGroup, TenantGroupPermission, TenantUserGroup)

    @classmethod
    def setUpClass(cls):
        # Django migrations do not create the shared, unmanaged tenant tables.
        with connection.schema_editor() as schema:
            for model in cls.tenant_models:
                schema.create_model(model)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        with connection.schema_editor() as schema:
            for model in reversed(cls.tenant_models):
                schema.delete_model(model)

    def test_manage_ai_settings_permission_seeded_by_migration(self):
        self.assertTrue(
            Permission.objects.filter(
                codename="manage_ai_settings",
                content_type__app_label="users",
                content_type__model="tenantintegration",
            ).exists()
        )

    def test_authorization_for_superadmin_tenant_admin_and_regular_user(self):
        tenant = Tenant.objects.create(name="Synthetic Org AI")
        superadmin = User.objects.create_superuser("ai_super", "super@synthetic.local", "StrongPass!23456")
        tenant_admin = User.objects.create_user("ai_tadmin", "tadmin@synthetic.local", "StrongPass!23456")
        regular_user = User.objects.create_user("ai_user", "user@synthetic.local", "StrongPass!23456")

        TenantMembership.objects.create(tenant=tenant, user_id=str(tenant_admin.id), role="TENANT_ADMIN")
        TenantMembership.objects.create(tenant=tenant, user_id=str(regular_user.id), role="USER")

        self.assertTrue(user_can_manage_ai_settings(superadmin))
        self.assertTrue(user_can_manage_ai_settings(tenant_admin))
        self.assertIn("manage_ai_settings", serialize_user_profile(tenant_admin)["active_permissions"])

        self.assertFalse(user_can_manage_ai_settings(regular_user))
        self.assertNotIn("manage_ai_settings", serialize_user_profile(regular_user)["active_permissions"])

        # Delegating via TenantGroupPermission grants access only inside that tenant.
        group = TenantGroup.objects.create(tenant=tenant, name="AI Operators")
        TenantGroupPermission.objects.create(group=group, permission_code="manage_ai_settings")
        TenantUserGroup.objects.create(tenant=tenant, user_id=str(regular_user.id), group=group)

        self.assertTrue(user_can_manage_ai_settings(regular_user, tenant_id=tenant.tenant_id))
        self.assertFalse(user_can_manage_ai_settings(regular_user, tenant_id="other-tenant-id"))

