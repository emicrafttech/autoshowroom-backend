from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dealers", "0006_dealerlocation_pending_changes"),
    ]

    operations = [
        migrations.AddField(
            model_name="dealerlocation",
            name="booking_availability",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
