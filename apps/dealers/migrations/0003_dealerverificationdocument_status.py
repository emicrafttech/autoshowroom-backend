from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dealers", "0002_dealerverificationdocument"),
    ]

    operations = [
        migrations.AddField(
            model_name="dealerverificationdocument",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="dealerverificationdocument",
            name="rejection_reason",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="dealerverificationdocument",
            name="reviewed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
