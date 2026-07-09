from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0004_booking_pending_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="attendance_status",
            field=models.CharField(
                choices=[
                    ("unknown", "Unknown"),
                    ("show", "Show"),
                    ("no_show", "No-show"),
                ],
                default="unknown",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="booking",
            name="attended_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
