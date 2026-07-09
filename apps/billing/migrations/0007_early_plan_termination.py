import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0006_billingplan_feed_priority"),
        ("dealers", "0007_dealerlocation_booking_availability"),
    ]

    operations = [
        migrations.CreateModel(
            name="EarlyPlanTermination",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("reason", models.TextField()),
                ("status", models.CharField(choices=[("open", "Open"), ("approved", "Approved"), ("declined", "Declined")], default="open", max_length=20)),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("decision_note", models.TextField(blank=True)),
                ("dealer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="early_plan_terminations", to="dealers.dealer")),
                ("plan", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="early_terminations", to="billing.billingplan")),
                ("subscription", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="early_terminations", to="billing.subscription")),
            ],
            options={"ordering": ["-requested_at"]},
        ),
    ]
