from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dealernotification",
            name="type",
            field=models.CharField(
                choices=[
                    ("review_issue", "Review issue"),
                    ("platform_message", "Platform message"),
                ],
                max_length=30,
            ),
        ),
    ]
