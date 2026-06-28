from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0004_subscription_pending_plan"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscription",
            name="paystack_authorization_code",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="subscription",
            name="payment_card_brand",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="subscription",
            name="payment_card_last4",
            field=models.CharField(blank=True, max_length=4),
        ),
        migrations.AddField(
            model_name="subscription",
            name="payment_card_exp_month",
            field=models.CharField(blank=True, max_length=2),
        ),
        migrations.AddField(
            model_name="subscription",
            name="payment_card_exp_year",
            field=models.CharField(blank=True, max_length=4),
        ),
    ]
