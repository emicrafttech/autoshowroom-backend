from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0003_remove_booking_otp"),
    ]

    operations = [
        migrations.AlterField(
            model_name="booking",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("confirmed", "Confirmed"),
                    ("rescheduled", "Rescheduled"),
                    ("cancelled", "Cancelled"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
    ]
