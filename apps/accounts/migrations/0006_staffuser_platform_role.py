from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("platform", "0003_platformrole_metadata"),
        ("accounts", "0005_staffuser_email_verification_required_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="staffuser",
            name="platform_role",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="staff_users",
                to="platform.platformrole",
            ),
        ),
    ]
