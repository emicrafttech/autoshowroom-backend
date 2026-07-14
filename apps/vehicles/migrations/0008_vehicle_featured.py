from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("vehicles", "0007_vehicle_listing_trust"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicle",
            name="is_featured",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="vehicle",
            name="featured_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="vehicle",
            name="featured_until",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="vehicle",
            index=models.Index(fields=["is_featured", "featured_until"], name="vehicles_ve_is_feat_idx"),
        ),
    ]
