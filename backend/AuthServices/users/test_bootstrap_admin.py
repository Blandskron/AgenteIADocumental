from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connections
from django.test import TransactionTestCase


class BootstrapAdminTests(TransactionTestCase):
    def run_command(self):
        output = StringIO()
        call_command("bootstrap_admin", stdout=output)
        return output.getvalue()

    def test_creates_once_and_never_resets_password_or_flags(self):
        with patch.dict("os.environ", {"INITIAL_ADMIN_USERNAME": "synthetic-admin", "INITIAL_ADMIN_PASSWORD": "synthetic-Strong-73924!"}):
            output = self.run_command()
        user = User.objects.get(username="synthetic-admin")
        self.assertTrue(user.is_staff and user.is_superuser and user.is_active)
        self.assertTrue(user.check_password("synthetic-Strong-73924!"))
        self.assertNotIn("synthetic-Strong-73924!", output)
        user.set_password("changed-Strong-84291!")
        user.is_active = False
        user.save()
        original = user.password
        with patch.dict("os.environ", {}, clear=True):
            self.run_command()
        user.refresh_from_db()
        self.assertEqual(user.password, original)
        self.assertFalse(user.is_active)
        self.assertEqual(User.objects.count(), 1)

    def test_invalid_configuration_creates_nothing_and_does_not_echo_values(self):
        for values in ({}, {"INITIAL_ADMIN_USERNAME": "synthetic-admin", "INITIAL_ADMIN_PASSWORD": "123"},
                       {"INITIAL_ADMIN_USERNAME": "bad name!", "INITIAL_ADMIN_PASSWORD": "synthetic-Strong-73924!"}):
            with self.subTest(values=list(values)), patch.dict("os.environ", values, clear=True):
                with self.assertRaises(CommandError) as error:
                    self.run_command()
                for value in values.values():
                    self.assertNotIn(value, str(error.exception))
                self.assertFalse(User.objects.exists())

    def test_does_not_promote_existing_normal_account(self):
        existing = User.objects.create_user(username="synthetic-admin", password="previous-Strong-87361!")
        with patch.dict("os.environ", {"INITIAL_ADMIN_USERNAME": existing.username, "INITIAL_ADMIN_PASSWORD": "synthetic-Strong-73924!"}):
            with self.assertRaises(CommandError):
                self.run_command()
        existing.refresh_from_db()
        self.assertFalse(existing.is_superuser)
        self.assertTrue(existing.check_password("previous-Strong-87361!"))

    def test_two_initializers_create_only_one_administrator(self):
        def initialize():
            try:
                return self.run_command()
            finally:
                connections.close_all()

        with patch.dict("os.environ", {"INITIAL_ADMIN_USERNAME": "synthetic-admin", "INITIAL_ADMIN_PASSWORD": "synthetic-Strong-73924!"}):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: initialize(), range(2)))
        self.assertEqual(User.objects.filter(is_superuser=True).count(), 1)
        self.assertEqual(sum("created" in result for result in results), 1)
