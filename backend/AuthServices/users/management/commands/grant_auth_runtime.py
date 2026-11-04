from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = "Concede al rol de ejecución los permisos de las tablas administradas por Django."

    @transaction.atomic
    def handle(self, *args, **options):
        tables = (
            "auth_group", "auth_group_permissions", "auth_permission", "auth_user",
            "auth_user_groups", "auth_user_user_permissions", "django_admin_log",
            "django_content_type", "django_session", "token_blacklist_blacklistedtoken",
            "token_blacklist_outstandingtoken", "users_loginattemptbudget",
        )
        with connection.cursor() as cursor:
            for table in tables:
                table_name = connection.ops.quote_name(table)
                cursor.execute(
                    f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.{table_name} TO auth_runtime"
                )
                if table not in {"django_session", "users_loginattemptbudget"}:
                    cursor.execute("SELECT pg_get_serial_sequence(%s, 'id')", [f"public.{table}"])
                    sequence = cursor.fetchone()[0]
                    if sequence is not None:
                        # pg_get_serial_sequence returns a SQL-qualified identifier.
                        cursor.execute(f"GRANT USAGE ON SEQUENCE {sequence} TO auth_runtime")
