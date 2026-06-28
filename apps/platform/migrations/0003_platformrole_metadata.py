from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("platform", "0002_platformsetting_securityincident_contentreportnote_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="platformrole",
            name="description",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="platformrole",
            name="color",
            field=models.CharField(default="#7aa2ff", max_length=24),
        ),
        migrations.AddField(
            model_name="platformrole",
            name="require_step_up",
            field=models.BooleanField(default=False),
        ),
    ]
