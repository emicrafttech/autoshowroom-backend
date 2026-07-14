from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dealers", "0007_dealerlocation_booking_availability"),
        ("billing", "0008_june_2026_plans"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dealer",
            name="plan_id",
            field=models.CharField(default="starter", max_length=40),
        ),
    ]
