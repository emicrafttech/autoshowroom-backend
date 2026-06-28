from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0002_billingdispute"),
    ]

    operations = [
        migrations.AddField(
            model_name="billingplan",
            name="stand_limit",
            field=models.PositiveIntegerField(default=1),
        ),
    ]
