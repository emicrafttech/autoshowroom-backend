from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dealers", "0004_dealerlocation_evidence_files"),
    ]

    operations = [
        migrations.AddField(
            model_name="dealer",
            name="booking_availability",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
