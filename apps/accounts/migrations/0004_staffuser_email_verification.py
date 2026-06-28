from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_dealersignupotp"),
    ]

    operations = [
        migrations.AddField(
            model_name="staffuser",
            name="email_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="staffuser",
            name="email_verification_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="staffuser",
            name="email_verification_token_hash",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
    ]
