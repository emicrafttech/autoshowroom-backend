import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("dealers", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Vehicle",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("slug", models.SlugField(max_length=160)),
                ("make", models.CharField(max_length=80)),
                ("model", models.CharField(max_length=120)),
                ("year", models.PositiveIntegerField()),
                ("trim", models.CharField(max_length=120)),
                ("price_ngn", models.PositiveBigIntegerField()),
                ("mileage_km", models.PositiveIntegerField()),
                ("transmission", models.CharField(choices=[("automatic", "Automatic"), ("manual", "Manual")], max_length=20)),
                ("fuel", models.CharField(choices=[("petrol", "Petrol"), ("diesel", "Diesel"), ("hybrid", "Hybrid"), ("electric", "Electric")], max_length=20)),
                ("colour", models.CharField(max_length=40)),
                ("body_type", models.CharField(choices=[("sedan", "Sedan"), ("suv", "SUV"), ("hatchback", "Hatchback"), ("pickup", "Pickup"), ("coupe", "Coupe"), ("van", "Van"), ("wagon", "Wagon"), ("convertible", "Convertible"), ("minivan", "Minivan")], max_length=20)),
                ("drivetrain", models.CharField(choices=[("fwd", "FWD"), ("rwd", "RWD"), ("awd", "AWD"), ("four_wd", "4WD")], max_length=20)),
                ("condition_grade", models.CharField(choices=[("excellent", "Excellent"), ("good", "Good"), ("fair", "Fair")], max_length=20)),
                ("negotiable", models.BooleanField(default=True)),
                ("notes", models.TextField(blank=True, null=True)),
                ("vin", models.CharField(blank=True, max_length=64, null=True)),
                ("chassis_number", models.CharField(blank=True, max_length=64, null=True)),
                ("import_type", models.CharField(blank=True, choices=[("tokunbo", "Tokunbo"), ("locally_used", "Locally used"), ("brand_new", "Brand new")], max_length=20, null=True)),
                ("year_of_manufacture", models.PositiveIntegerField(blank=True, null=True)),
                ("engine_capacity_cc", models.PositiveIntegerField(blank=True, null=True)),
                ("registration_plate", models.CharField(blank=True, max_length=32, null=True)),
                ("registration_state", models.CharField(blank=True, max_length=80, null=True)),
                ("registration_lga", models.CharField(blank=True, max_length=120, null=True)),
                ("customs_duty_status", models.CharField(choices=[("cleared", "Cleared"), ("pending", "Pending"), ("unknown", "Unknown"), ("not_applicable", "Not applicable")], default="unknown", max_length=20)),
                ("customs_reference", models.CharField(blank=True, max_length=120, null=True)),
                ("customs_cleared_at", models.DateTimeField(blank=True, null=True)),
                ("body_history", models.CharField(choices=[("first_body", "First body"), ("repaint", "Repaint"), ("accident_recorded", "Accident recorded"), ("unknown", "Unknown")], default="unknown", max_length=30)),
                ("papers_status", models.CharField(choices=[("complete", "Complete"), ("partial", "Partial"), ("unknown", "Unknown")], default="unknown", max_length=20)),
                ("duty_paid_claim", models.CharField(choices=[("unverified", "Unverified"), ("dealer_claimed", "Dealer claimed"), ("api_verified", "API verified"), ("manually_verified", "Manually verified")], default="unverified", max_length=30)),
                ("duty_paid_verified_at", models.DateTimeField(blank=True, null=True)),
                ("status", models.CharField(choices=[("available", "Available"), ("reserved", "Reserved"), ("sold", "Sold"), ("hidden", "Hidden")], default="hidden", max_length=20)),
                ("listing_verification_status", models.CharField(choices=[("draft", "Draft"), ("pending_review", "Pending review"), ("approved", "Approved"), ("rejected", "Rejected")], default="draft", max_length=30)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("dealer_attestation_at", models.DateTimeField(blank=True, null=True)),
                ("listing_approved_at", models.DateTimeField(blank=True, null=True)),
                ("listing_rejected_reason", models.TextField(blank=True, null=True)),
                ("feed_ready", models.BooleanField(default=False)),
                ("refreshed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("dealer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="vehicles", to="dealers.dealer")),
                ("location", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="vehicles", to="dealers.dealerlocation")),
            ],
            options={
                "ordering": ["-updated_at"],
                "indexes": [
                    models.Index(fields=["dealer", "status"], name="vehicles_ve_dealer__569480_idx"),
                    models.Index(fields=["dealer", "location"], name="vehicles_ve_dealer__8cd416_idx"),
                    models.Index(fields=["listing_verification_status"], name="vehicles_ve_listing_433c21_idx"),
                    models.Index(fields=["make", "model"], name="vehicles_ve_make_6615f9_idx"),
                    models.Index(fields=["slug"], name="vehicles_ve_slug_2cc435_idx"),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="vehicle",
            constraint=models.UniqueConstraint(fields=("dealer", "slug"), name="unique_vehicle_slug_per_dealer"),
        ),
    ]
