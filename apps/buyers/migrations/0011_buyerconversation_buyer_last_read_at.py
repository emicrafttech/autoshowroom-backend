from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("buyers", "0010_buyerconversation_dealer_last_read_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="buyerconversation",
            name="buyer_last_read_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
