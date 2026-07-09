from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("vehicles", "0006_vehiclepricehistory"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicle",
            name="listing_trust",
            field=models.TextField(blank=True, null=True),
        ),
    ]
