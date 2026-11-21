from django.db import migrations, models
import django.utils.timezone
import users.models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_tenantintegration_and_ai_permission"),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("audit_id", models.TextField(default=users.models.make_uuid, primary_key=True, serialize=False)),
                ("actor_user_id", models.TextField(blank=True, null=True)),
                ("action", models.TextField()),
                ("resource_type", models.TextField()),
                ("resource_id", models.TextField(blank=True, null=True)),
                ("target_user_id", models.TextField(blank=True, null=True)),
                ("ip_address", models.TextField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True, null=True)),
                ("metadata", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={
                "db_table": "audit_logs",
                "managed": False,
            },
        ),
    ]
