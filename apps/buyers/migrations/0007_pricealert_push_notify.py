from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("buyers", "0006_pricealert_blockeddealer"),
    ]

    operations = [
        migrations.AddField(
            model_name="pricealert",
            name="push_notify",
            field=models.BooleanField(default=True),
        ),
    ]
