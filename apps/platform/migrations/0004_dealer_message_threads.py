import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("dealers", "0007_dealerlocation_booking_availability"),
        ("platform", "0003_platformrole_metadata"),
    ]

    operations = [
        migrations.CreateModel(
            name="DealerMessageThread",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("subject", models.CharField(max_length=200)),
                ("status", models.CharField(choices=[("open", "Open"), ("closed", "Closed")], default="open", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_dealer_threads", to="accounts.staffuser")),
                ("dealer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="message_threads", to="dealers.dealer")),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        migrations.CreateModel(
            name="DealerMessage",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("sender_type", models.CharField(choices=[("platform", "Platform"), ("dealer", "Dealer")], max_length=20)),
                ("body", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("sender", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="dealer_thread_messages", to="accounts.staffuser")),
                ("thread", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="platform.dealermessagethread")),
            ],
            options={"ordering": ["created_at"]},
        ),
    ]
