from django.db import migrations, models
import django.utils.timezone
import users.models


def seed_manage_ai_settings_permission(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    content_type, _ = ContentType.objects.get_or_create(
        app_label="users",
        model="tenantintegration",
    )
    Permission.objects.get_or_create(
        codename="manage_ai_settings",
        content_type=content_type,
        defaults={"name": "Can manage AI provider settings"},
    )


def remove_manage_ai_settings_permission(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    content_type = ContentType.objects.filter(app_label="users", model="tenantintegration").first()
    if content_type:
        Permission.objects.filter(codename="manage_ai_settings", content_type=content_type).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_loginattemptbudget"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.CreateModel(
            name="TenantIntegration",
            fields=[
                ("integration_id", models.TextField(default=users.models.make_uuid, primary_key=True, serialize=False)),
                ("provider", models.TextField()),
                ("status", models.TextField(default="DISABLED")),
                ("enabled_for_roles", models.JSONField(default=list)),
                ("config", models.JSONField(default=dict)),
                ("secrets_encrypted", models.TextField(blank=True, null=True)),
                ("updated_by_user_id", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={
                "db_table": "tenant_integrations",
                "managed": False,
            },
        ),
        migrations.RunPython(
            seed_manage_ai_settings_permission,
            reverse_code=remove_manage_ai_settings_permission,
        ),
    ]

