from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dealers", "0003_dealerverificationdocument_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="dealerlocation",
            name="evidence_files",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
