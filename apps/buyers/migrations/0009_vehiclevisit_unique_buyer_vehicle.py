from django.db import migrations, models
from django.db.models import Count, Max


def dedupe_vehicle_visits(apps, schema_editor):
    VehicleVisit = apps.get_model("buyers", "VehicleVisit")
    duplicates = (
        VehicleVisit.objects.values("buyer_id", "vehicle_id")
        .annotate(latest=Max("created_at"), total=Count("id"))
        .filter(total__gt=1)
    )
    for row in duplicates:
        visits = VehicleVisit.objects.filter(
            buyer_id=row["buyer_id"],
            vehicle_id=row["vehicle_id"],
        ).order_by("-created_at", "-id")
        keep_id = visits.values_list("id", flat=True).first()
        visits.exclude(id=keep_id).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("buyers", "0008_buyerpushdevice"),
    ]

    operations = [
        migrations.RunPython(dedupe_vehicle_visits, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="vehiclevisit",
            constraint=models.UniqueConstraint(
                fields=("buyer", "vehicle"),
                name="unique_buyer_vehicle_visit",
            ),
        ),
    ]
