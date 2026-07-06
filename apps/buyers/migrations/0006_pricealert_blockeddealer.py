import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dealers", "0005_dealer_booking_availability"),
        ("buyers", "0005_buyermessage_attachment_url"),
    ]

    operations = [
        migrations.CreateModel(
            name="PriceAlert",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=160)),
                ("body_type", models.CharField(blank=True, default="", max_length=20)),
                ("make", models.CharField(blank=True, default="", max_length=80)),
                ("model", models.CharField(blank=True, default="", max_length=120)),
                ("min_year", models.PositiveIntegerField(blank=True, null=True)),
                ("max_price_ngn", models.PositiveBigIntegerField(blank=True, null=True)),
                ("min_price_ngn", models.PositiveBigIntegerField(blank=True, null=True)),
                ("area", models.CharField(blank=True, default="", max_length=120)),
                (
                    "icon_kind",
                    models.CharField(
                        choices=[("car", "Car"), ("clock", "Clock"), ("pulse", "Pulse")],
                        default="car",
                        max_length=20,
                    ),
                ),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "buyer",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="price_alerts",
                        to="buyers.buyer",
                    ),
                ),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        migrations.CreateModel(
            name="BlockedDealer",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "buyer",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="blocked_dealers",
                        to="buyers.buyer",
                    ),
                ),
                (
                    "dealer",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="blocked_by_buyers",
                        to="dealers.dealer",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="blockeddealer",
            constraint=models.UniqueConstraint(
                fields=("buyer", "dealer"),
                name="unique_blocked_dealer_per_buyer",
            ),
        ),
    ]
