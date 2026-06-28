from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_staffuser_platform_role"),
        ("dealers", "0004_dealerlocation_evidence_files"),
        ("vehicles", "0004_vehiclereviewissue"),
        ("notifications", "0002_platform_message_notification_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlatformNotification",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("type", models.CharField(max_length=40, choices=[
                    ("listing_review_submitted", "Listing review submitted"),
                    ("dealer_verification_submitted", "Dealer verification submitted"),
                    ("content_report_filed", "Content report filed"),
                    ("sanction_appeal_submitted", "Sanction appeal submitted"),
                ])),
                ("title", models.CharField(max_length=180)),
                ("body", models.TextField()),
                ("href", models.CharField(blank=True, max_length=255)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("dealer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="platform_notifications", to="dealers.dealer")),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="platform_notifications", to="accounts.staffuser")),
                ("vehicle", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="platform_notifications", to="vehicles.vehicle")),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["recipient", "read_at"], name="notificatio_recipie_0d0f8d_idx"),
                    models.Index(fields=["created_at"], name="notificatio_created_8e4b0a_idx"),
                ],
            },
        ),
    ]
