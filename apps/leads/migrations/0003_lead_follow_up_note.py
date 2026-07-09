import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("leads", "0002_genericuploadrequest_analyticsevent"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="follow_up_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="lead",
            name="source",
            field=models.CharField(
                choices=[
                    ("feed", "Feed"),
                    ("whatsapp", "WhatsApp"),
                    ("call", "Call"),
                    ("booking", "Booking"),
                    ("notify_me", "Notify me"),
                    ("walk_in", "Walk-in"),
                ],
                default="feed",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="LeadNote",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("body", models.TextField()),
                ("shared_with_team", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "author",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="lead_notes",
                        to="accounts.staffuser",
                    ),
                ),
                (
                    "lead",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notes",
                        to="leads.lead",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
