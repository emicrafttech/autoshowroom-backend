import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("vehicles", "0005_vehiclemedia_processing_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="VehiclePriceHistory",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("price_ngn", models.PositiveBigIntegerField()),
                ("recorded_at", models.DateTimeField(auto_now_add=True)),
                (
                    "vehicle",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="price_history",
                        to="vehicles.vehicle",
                    ),
                ),
            ],
            options={"ordering": ["-recorded_at"]},
        ),
        migrations.AddIndex(
            model_name="vehiclepricehistory",
            index=models.Index(fields=["vehicle", "-recorded_at"], name="vehicles_ve_vehicle_0a8f2d_idx"),
        ),
    ]
