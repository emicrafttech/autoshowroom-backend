from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("buyers", "0004_buyer_profile_extras"),
    ]

    operations = [
        migrations.AddField(
            model_name="buyermessage",
            name="attachment_url",
            field=models.URLField(blank=True, default="", max_length=500),
        ),
        migrations.AlterField(
            model_name="buyermessage",
            name="body",
            field=models.TextField(blank=True, default=""),
        ),
    ]
