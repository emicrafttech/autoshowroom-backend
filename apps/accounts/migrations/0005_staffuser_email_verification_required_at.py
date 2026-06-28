from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_staffuser_email_verification"),
    ]

    operations = [
        migrations.AddField(
            model_name="staffuser",
            name="email_verification_required_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
