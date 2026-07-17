from django.core.management.base import BaseCommand
from django.db import transaction

from apps.vehicles.catalog import get_full_catalog, reload_catalog
from apps.vehicles.models import VehicleMake, VehicleModel


class Command(BaseCommand):
    help = "Sync VehicleMake/VehicleModel tables from vehicle_catalog.json."

    def add_arguments(self, parser):
        parser.add_argument(
            "--deactivate-missing",
            action="store_true",
            help="Mark makes/models absent from the JSON catalog as inactive.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        reload_catalog()
        catalog = get_full_catalog()
        seen_make_ids: set[int] = set()
        seen_model_ids: set[int] = set()
        make_count = 0
        model_count = 0

        for make_order, make_entry in enumerate(catalog["makes"], start=1):
            make_name = str(make_entry["name"]).strip()
            if not make_name:
                continue
            make, _ = VehicleMake.objects.update_or_create(
                name=make_name,
                defaults={"display_order": make_order, "is_active": True},
            )
            seen_make_ids.add(make.id)
            make_count += 1

            for model_order, model_entry in enumerate(make_entry.get("models", []), start=1):
                model_name = str(model_entry.get("name", "")).strip()
                if not model_name:
                    continue
                model, _ = VehicleModel.objects.update_or_create(
                    make=make,
                    name=model_name,
                    defaults={"display_order": model_order, "is_active": True},
                )
                seen_model_ids.add(model.id)
                model_count += 1

        deactivated_makes = 0
        deactivated_models = 0
        if options["deactivate_missing"]:
            deactivated_makes = VehicleMake.objects.exclude(id__in=seen_make_ids).update(
                is_active=False
            )
            deactivated_models = VehicleModel.objects.exclude(id__in=seen_model_ids).update(
                is_active=False
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Synced {make_count} makes and {model_count} models from JSON catalog."
            )
        )
        if options["deactivate_missing"]:
            self.stdout.write(
                f"Deactivated {deactivated_makes} makes and {deactivated_models} models."
            )
