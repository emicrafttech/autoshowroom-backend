import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("buyers", "0007_pricealert_push_notify"),
    ]

    operations = [
        migrations.CreateModel(
            name="BuyerPushDevice",
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
                    "buyer",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="push_devices",
                        to="buyers.buyer",
                    ),
                ),
            ],
            options={
                "ordering": ["-last_seen_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="buyerpushdevice",
            constraint=models.UniqueConstraint(
                fields=("buyer", "fcm_token"),
                name="unique_buyer_push_token",
            ),
        ),
    ]
