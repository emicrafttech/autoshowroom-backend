import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("accounts", "0003_dealersignupotp"),
        ("dealers", "0002_dealerverificationdocument"),
        ("vehicles", "0004_vehiclereviewissue"),
    ]

    operations = [
        migrations.CreateModel(
            name="DealerNotification",
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
                    "type",
                    models.CharField(
                        choices=[("review_issue", "Review issue")],
                        max_length=30,
                    ),
                ),
                ("title", models.CharField(max_length=180)),
                ("body", models.TextField()),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "dealer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to="dealers.dealer",
                    ),
                ),
                (
                    "recipient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to="accounts.staffuser",
                    ),
                ),
                (
                    "review_issue",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to="vehicles.vehiclereviewissue",
                    ),
                ),
                (
                    "vehicle",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to="vehicles.vehicle",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["recipient", "read_at"],
                        name="notificatio_recipie_bbb187_idx",
                    ),
                    models.Index(
                        fields=["dealer", "created_at"],
                        name="notificatio_dealer__dc2bc7_idx",
                    ),
                ],
            },
        ),
    ]
