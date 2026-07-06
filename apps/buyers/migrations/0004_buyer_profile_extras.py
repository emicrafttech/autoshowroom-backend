from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("buyers", "0003_buyerotp_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="buyer",
            name="bio",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="buyer",
            name="location",
            field=models.CharField(blank=True, default="", max_length=160),
        ),
        migrations.AddField(
            model_name="buyer",
            name="photo_url",
            field=models.URLField(blank=True, default="", max_length=500),
        ),
    ]
