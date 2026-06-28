import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_dealersignupotp"),
        ("vehicles", "0003_vehiclemedia_vehicle_cover_media"),
    ]

    operations = [
        migrations.CreateModel(
            name="VehicleReviewIssue",
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
                    "status",
                    models.CharField(
                        choices=[
                            ("open", "Open"),
                            ("resolved", "Resolved"),
                            ("approved", "Approved"),
                            ("dismissed", "Dismissed"),
                        ],
                        default="open",
                        max_length=20,
                    ),
                ),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("details", "Details"),
                            ("price", "Price"),
                            ("media", "Media"),
                            ("documents", "Documents"),
                            ("compliance", "Compliance"),
                            ("other", "Other"),
                        ],
                        default="other",
                        max_length=30,
                    ),
                ),
                ("message", models.TextField()),
                ("dealer_response", models.TextField(blank=True, null=True)),
                ("vehicle_snapshot", models.JSONField(blank=True, default=dict)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "reviewer",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="vehicle_review_issues",
                        to="accounts.staffuser",
                    ),
                ),
                (
                    "vehicle",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="review_issues",
                        to="vehicles.vehicle",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["vehicle", "status"],
                        name="vehicles_ve_vehicle_e57b7b_idx",
                    ),
                    models.Index(
                        fields=["reviewer", "status"],
                        name="vehicles_ve_reviewer_0efb69_idx",
                    ),
                ],
            },
        ),
    ]
