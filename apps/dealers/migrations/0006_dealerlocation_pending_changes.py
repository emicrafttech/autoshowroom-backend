from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dealers", "0005_dealer_booking_availability"),
    ]

    operations = [
        migrations.AddField(
            model_name="dealerlocation",
            name="pending_changes",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="dealerlocation",
            name="pending_changes_submitted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="dealerlocation",
            name="pending_changes_reviewed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="dealerlocation",
            name="pending_changes_rejection_reason",
            field=models.TextField(blank=True, null=True),
        ),
    ]
