import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Dealer",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("slug", models.SlugField(unique=True)),
                ("name", models.CharField(max_length=160)),
                ("legal_name", models.CharField(max_length=200)),
                (
                    "entity_type",
                    models.CharField(
                        choices=[
                            ("registered_company", "Registered company"),
                            ("sole_proprietor", "Sole proprietor"),
                        ],
                        default="registered_company",
                        max_length=40,
                    ),
                ),
                (
                    "verification_status",
                    models.CharField(
                        choices=[
                            ("not_submitted", "Not submitted"),
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                        ],
                        default="not_submitted",
                        max_length=30,
                    ),
                ),
                (
                    "operational_status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("suspended", "Suspended"),
                            ("banned", "Banned"),
                        ],
                        default="active",
                        max_length=20,
                    ),
                ),
                ("suspended_at", models.DateTimeField(blank=True, null=True)),
                ("suspended_reason", models.TextField(blank=True, null=True)),
                ("verified_badge", models.BooleanField(default=False)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("area", models.CharField(max_length=120)),
                ("city_slug", models.SlugField(default="abuja")),
                ("district_slug", models.SlugField(blank=True, null=True)),
                ("address", models.TextField(blank=True, null=True)),
                ("latitude", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ("longitude", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ("phone", models.CharField(max_length=32)),
                ("whatsapp", models.CharField(blank=True, max_length=32, null=True)),
                ("logo_url", models.URLField(blank=True, null=True)),
                ("description", models.TextField(blank=True, null=True)),
                ("hours", models.JSONField(blank=True, default=dict)),
                ("plan_id", models.CharField(default="free", max_length=40)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="DealerLocation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=80)),
                ("area", models.CharField(max_length=120)),
                ("city_slug", models.SlugField(default="abuja")),
                ("district_slug", models.SlugField(blank=True, null=True)),
                ("address", models.TextField(blank=True, null=True)),
                ("latitude", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ("longitude", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ("is_primary", models.BooleanField(default=False)),
                (
                    "premises_verification_status",
                    models.CharField(
                        choices=[
                            ("not_submitted", "Not submitted"),
                            ("pending", "Pending"),
                            ("verified", "Verified"),
                            ("rejected", "Rejected"),
                        ],
                        default="not_submitted",
                        max_length=30,
                    ),
                ),
                ("premises_verified_at", models.DateTimeField(blank=True, null=True)),
                ("premises_rejected_at", models.DateTimeField(blank=True, null=True)),
                ("premises_rejection_reason", models.TextField(blank=True, null=True)),
                ("geo_changed_at", models.DateTimeField(blank=True, null=True)),
                ("pending_geo", models.JSONField(blank=True, null=True)),
                ("premises_rejection_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "dealer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="locations",
                        to="dealers.dealer",
                    ),
                ),
            ],
            options={"ordering": ["-is_primary", "name"]},
        ),
        migrations.AddConstraint(
            model_name="dealerlocation",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_primary", True)),
                fields=("dealer",),
                name="unique_primary_location_per_dealer",
            ),
        ),
    ]
