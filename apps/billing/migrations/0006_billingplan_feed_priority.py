from django.db import migrations, models


def seed_feed_priority(apps, schema_editor):
    BillingPlan = apps.get_model("billing", "BillingPlan")
    defaults = {
        "free": 0,
        "growth": 10,
        "enterprise": 20,
    }
    for plan_id, priority in defaults.items():
        BillingPlan.objects.filter(id=plan_id).update(feed_priority=priority)


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0005_subscription_payment_method"),
    ]

    operations = [
        migrations.AddField(
            model_name="billingplan",
            name="feed_priority",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.RunPython(seed_feed_priority, migrations.RunPython.noop),
    ]
