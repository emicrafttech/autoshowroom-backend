from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("buyers", "0009_vehiclevisit_unique_buyer_vehicle"),
    ]

    operations = [
        migrations.AddField(
            model_name="buyerconversation",
            name="dealer_last_read_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
