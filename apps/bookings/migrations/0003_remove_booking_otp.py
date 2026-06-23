from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0002_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="booking",
            name="otp_code",
        ),
        migrations.RemoveField(
            model_name="booking",
            name="otp_verified_at",
        ),
        migrations.AlterField(
            model_name="booking",
            name="status",
            field=models.CharField(
                choices=[
                    ("confirmed", "Confirmed"),
                    ("rescheduled", "Rescheduled"),
                    ("cancelled", "Cancelled"),
                ],
                default="confirmed",
                max_length=20,
            ),
        ),
    ]
