import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import connection, transaction


class Command(BaseCommand):
    help = "Create the initial administrator once, preserving all existing accounts."

    @transaction.atomic
    def handle(self, *args, **options):
        # Serialize independent Compose runs as well as scaled initialization jobs.
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", ["blandskron.auth.bootstrap"])
        users = get_user_model()
        if users.objects.filter(is_superuser=True).exists():
            self.stdout.write("Existing administrator preserved.")
            return

        username = os.environ.get("INITIAL_ADMIN_USERNAME", "")
        password = os.environ.get("INITIAL_ADMIN_PASSWORD", "")
        email = os.environ.get("INITIAL_ADMIN_EMAIL", "")
        if not username or username != username.strip() or not password:
            raise CommandError("Set INITIAL_ADMIN_USERNAME and INITIAL_ADMIN_PASSWORD for the first installation.")
        username = users.normalize_username(username)
        if users.objects.filter(username=username).exists():
            raise CommandError("Initial administrator name is already occupied; existing account preserved.")
        user = users(username=username, email=email, is_staff=True, is_superuser=True, is_active=True)
        try:
            if email:
                validate_email(email)
            user.full_clean(exclude=["password"])
            validate_password(password, user=user)
        except ValidationError:
            # Validation messages can contain the supplied value; never echo secrets.
            raise CommandError("Invalid initial administrator configuration; check username, email and password policy.") from None
        user.set_password(password)
        user.save()
        self.stdout.write("Initial administrator created.")
