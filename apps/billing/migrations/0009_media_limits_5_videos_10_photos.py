from django.db import migrations, models

from apps.billing.plan_catalogue import upsert_plans


def apply_media_limits(apps, schema_editor):
    BillingPlan = apps.get_model("billing", "BillingPlan")
    upsert_plans(BillingPlan)


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0008_june_2026_plans"),
    ]

    operations = [
        migrations.AlterField(
            model_name="billingplan",
            name="photos_per_vehicle",
            field=models.PositiveSmallIntegerField(default=10),
        ),
        migrations.RunPython(apply_media_limits, migrations.RunPython.noop),
    ]
