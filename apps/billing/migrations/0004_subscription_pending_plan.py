import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0003_billingplan_stand_limit"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscription",
            name="pending_plan",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="pending_subscriptions",
                to="billing.billingplan",
            ),
        ),
        migrations.AddField(
            model_name="subscription",
            name="pending_plan_effective_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
