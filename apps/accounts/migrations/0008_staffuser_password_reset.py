from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_dealerpushdevice"),
    ]

    operations = [
        migrations.AddField(
            model_name="staffuser",
            name="password_reset_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="staffuser",
            name="password_reset_token_hash",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
    ]
