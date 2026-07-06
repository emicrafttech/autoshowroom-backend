from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("vehicles", "0004_vehiclereviewissue"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehiclemedia",
            name="original_s3_key",
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name="vehiclemedia",
            name="original_url",
            field=models.URLField(blank=True, max_length=1000, null=True),
        ),
        migrations.AddField(
            model_name="vehiclemedia",
            name="processed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
