import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_staffuser_platform_role"),
    ]

    operations = [
        migrations.CreateModel(
            name="DealerPushDevice",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("fcm_token", models.CharField(max_length=512)),
                (
                    "platform",
                    models.CharField(
                        choices=[("android", "Android"), ("ios", "iOS")],
                        default="android",
                        max_length=20,
                    ),
                ),
                ("last_seen_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "staff_user",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="push_devices",
                        to="accounts.staffuser",
                    ),
                ),
            ],
            options={
                "ordering": ["-last_seen_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="dealerpushdevice",
            constraint=models.UniqueConstraint(
                fields=("staff_user", "fcm_token"),
                name="unique_dealer_push_token",
            ),
        ),
    ]
