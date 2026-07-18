from django.db import migrations, models


def clear_placeholder_trims(apps, schema_editor):
    Vehicle = apps.get_model("vehicles", "Vehicle")
    Vehicle.objects.filter(trim__iexact="not specified").update(trim="")


class Migration(migrations.Migration):
    dependencies = [
        ("vehicles", "0008_vehicle_featured"),
    ]

    operations = [
        migrations.AlterField(
            model_name="vehicle",
            name="trim",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.RunPython(clear_placeholder_trims, migrations.RunPython.noop),
    ]
