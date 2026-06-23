import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("vehicles", "0002_vehiclemake_vehiclemodel_seed_catalog"),
    ]

    operations = [
        migrations.CreateModel(
            name="VehicleMedia",
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
                (
                    "kind",
                    models.CharField(
                        choices=[("photo", "Photo"), ("video", "Video")],
                        max_length=20,
                    ),
                ),
                ("url", models.URLField(max_length=1000)),
                ("thumbnail_url", models.URLField(blank=True, max_length=1000, null=True)),
                ("content_type", models.CharField(max_length=120)),
                ("file_name", models.CharField(max_length=255)),
                ("file_size", models.PositiveBigIntegerField(blank=True, null=True)),
                ("s3_key", models.CharField(max_length=500, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending_upload", "Pending upload"),
                            ("uploaded", "Uploaded"),
                            ("processing", "Processing"),
                            ("ready", "Ready"),
                            ("failed", "Failed"),
                        ],
                        default="pending_upload",
                        max_length=20,
                    ),
                ),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("upload_expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "vehicle",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="media_items",
                        to="vehicles.vehicle",
                    ),
                ),
            ],
            options={
                "ordering": ["sort_order", "created_at"],
                "indexes": [
                    models.Index(
                        fields=["vehicle", "sort_order"],
                        name="vehicles_ve_vehicle_0a65b3_idx",
                    ),
                    models.Index(
                        fields=["vehicle", "status"],
                        name="vehicles_ve_vehicle_e99168_idx",
                    ),
                ],
            },
        ),
        migrations.AddField(
            model_name="vehicle",
            name="cover_media",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="vehicles.vehiclemedia",
            ),
        ),
    ]
