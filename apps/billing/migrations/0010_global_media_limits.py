from django.db import migrations, models

from apps.billing.plan_catalogue import upsert_plans


def apply_global_media_limits(apps, schema_editor):
    BillingPlan = apps.get_model("billing", "BillingPlan")
    upsert_plans(BillingPlan)


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0009_media_limits_5_videos_10_photos"),
    ]

    operations = [
        migrations.AlterField(
            model_name="billingplan",
            name="videos_per_vehicle",
            field=models.PositiveSmallIntegerField(default=8),
        ),
        migrations.AlterField(
            model_name="billingplan",
            name="photos_per_vehicle",
            field=models.PositiveSmallIntegerField(default=30),
        ),
        migrations.AlterField(
            model_name="billingplan",
            name="max_clip_seconds",
            field=models.PositiveIntegerField(default=180),
        ),
        migrations.RunPython(apply_global_media_limits, migrations.RunPython.noop),
    ]
