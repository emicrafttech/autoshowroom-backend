from django.db import migrations, models
import django.db.models.deletion


CATALOG = {
    "Acura": ["ILX", "MDX", "RDX", "RLX", "TL", "TLX", "TSX", "ZDX"],
    "Alfa Romeo": ["Giulia", "Stelvio"],
    "Audi": ["A3", "A4", "A5", "A6", "A7", "A8", "Q3", "Q5", "Q7", "Q8", "TT"],
    "Bentley": ["Bentayga", "Continental GT", "Flying Spur", "Mulsanne"],
    "BMW": ["1 Series", "2 Series", "3 Series", "4 Series", "5 Series", "7 Series", "X1", "X3", "X4", "X5", "X6", "X7"],
    "Buick": ["Enclave", "Encore", "LaCrosse", "Regal"],
    "Cadillac": ["Escalade", "SRX", "XT4", "XT5", "XT6"],
    "Chevrolet": ["Camaro", "Captiva", "Cruze", "Equinox", "Malibu", "Silverado", "Spark", "Suburban", "Tahoe", "Trailblazer"],
    "Chrysler": ["200", "300", "Pacifica", "Town & Country"],
    "Citroen": ["Berlingo", "C3", "C4", "C5 Aircross"],
    "Dodge": ["Challenger", "Charger", "Durango", "Journey", "Ram"],
    "Fiat": ["500", "Doblo", "Panda", "Tipo"],
    "Ford": ["Edge", "Escape", "Expedition", "Explorer", "F-150", "Fiesta", "Focus", "Fusion", "Mustang", "Ranger", "Transit"],
    "Genesis": ["G70", "G80", "GV70", "GV80"],
    "GMC": ["Acadia", "Sierra", "Terrain", "Yukon"],
    "Honda": ["Accord", "City", "Civic", "CR-V", "Crosstour", "Element", "Fit", "HR-V", "Odyssey", "Passport", "Pilot", "Ridgeline"],
    "Hummer": ["H2", "H3"],
    "Hyundai": ["Accent", "Azera", "Creta", "Elantra", "Genesis", "Grand i10", "Santa Fe", "Sonata", "Tucson", "Veloster", "Venue", "Veracruz"],
    "Infiniti": ["EX", "FX", "G35", "G37", "JX", "M", "Q50", "Q60", "QX50", "QX56", "QX60", "QX70", "QX80"],
    "Isuzu": ["D-Max", "MU-X", "Rodeo"],
    "Jaguar": ["E-Pace", "F-Pace", "F-Type", "XE", "XF", "XJ"],
    "Jeep": ["Cherokee", "Compass", "Gladiator", "Grand Cherokee", "Liberty", "Patriot", "Renegade", "Wrangler"],
    "Kia": ["Carens", "Carnival", "Cerato", "Forte", "K5", "Mohave", "Niro", "Optima", "Picanto", "Rio", "Seltos", "Sorento", "Soul", "Sportage", "Telluride"],
    "Land Rover": ["Defender", "Discovery", "Discovery Sport", "Freelander", "LR2", "LR3", "LR4", "Range Rover", "Range Rover Evoque", "Range Rover Sport", "Range Rover Velar"],
    "Lexus": ["CT", "ES", "GS", "GX", "HS", "IS", "LC", "LS", "LX", "NX", "RC", "RX", "UX"],
    "Lincoln": ["Aviator", "Continental", "MKC", "MKS", "MKT", "MKX", "MKZ", "Navigator", "Nautilus"],
    "Maserati": ["Ghibli", "GranTurismo", "Levante", "Quattroporte"],
    "Mazda": ["2", "3", "5", "6", "CX-3", "CX-30", "CX-5", "CX-7", "CX-9", "MX-5 Miata", "Tribute"],
    "Mercedes-Benz": ["A-Class", "B-Class", "C-Class", "CLA", "CLS", "E-Class", "G-Class", "GL", "GLA", "GLB", "GLC", "GLE", "GLK", "GLS", "M-Class", "S-Class", "Sprinter", "V-Class"],
    "Mini": ["Clubman", "Cooper", "Countryman", "Paceman"],
    "Mitsubishi": ["ASX", "Eclipse Cross", "Galant", "L200", "Lancer", "Montero", "Outlander", "Pajero", "Pajero Sport"],
    "Nissan": ["350Z", "370Z", "Almera", "Altima", "Armada", "Frontier", "Juke", "Maxima", "Murano", "Navara", "Pathfinder", "Patrol", "Qashqai", "Rogue", "Sentra", "Teana", "Titan", "X-Trail", "Xterra"],
    "Peugeot": ["206", "207", "208", "3008", "301", "307", "308", "406", "407", "508", "5008", "Partner", "Rifter"],
    "Porsche": ["911", "Boxster", "Cayenne", "Cayman", "Macan", "Panamera", "Taycan"],
    "Ram": ["1500", "2500", "3500", "ProMaster"],
    "Renault": ["Captur", "Clio", "Duster", "Koleos", "Logan", "Megane"],
    "Rolls-Royce": ["Cullinan", "Ghost", "Phantom", "Wraith"],
    "Seat": ["Alhambra", "Ateca", "Ibiza", "Leon"],
    "Skoda": ["Fabia", "Kodiaq", "Octavia", "Superb", "Yeti"],
    "Subaru": ["Ascent", "Forester", "Impreza", "Legacy", "Outback", "Tribeca", "WRX", "XV"],
    "Suzuki": ["Baleno", "Ciaz", "Grand Vitara", "Jimny", "Swift", "Vitara"],
    "Tesla": ["Model 3", "Model S", "Model X", "Model Y"],
    "Toyota": ["4Runner", "Avalon", "Avensis", "Camry", "Celica", "Coaster", "Corolla", "Crown", "FJ Cruiser", "Fortuner", "HiAce", "Highlander", "Hilux", "Land Cruiser", "Matrix", "Prado", "Prius", "RAV4", "Sequoia", "Sienna", "Tacoma", "Tundra", "Venza", "Yaris"],
    "Volkswagen": ["Amarok", "Arteon", "Beetle", "CC", "Golf", "Jetta", "Passat", "Polo", "Sharan", "Tiguan", "Touareg", "Transporter"],
    "Volvo": ["C30", "S40", "S60", "S80", "S90", "V40", "V60", "XC40", "XC60", "XC70", "XC90"],
}


def seed_catalog(apps, schema_editor):
    vehicle_make = apps.get_model("vehicles", "VehicleMake")
    vehicle_model = apps.get_model("vehicles", "VehicleModel")

    for make_order, (make_name, model_names) in enumerate(CATALOG.items(), start=1):
        make, _ = vehicle_make.objects.update_or_create(
            name=make_name,
            defaults={"display_order": make_order, "is_active": True},
        )
        for model_order, model_name in enumerate(model_names, start=1):
            vehicle_model.objects.update_or_create(
                make=make,
                name=model_name,
                defaults={"display_order": model_order, "is_active": True},
            )


def unseed_catalog(apps, schema_editor):
    vehicle_make = apps.get_model("vehicles", "VehicleMake")
    vehicle_make.objects.filter(name__in=CATALOG.keys()).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("vehicles", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="VehicleMake",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80, unique=True)),
                ("display_order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["display_order", "name"]},
        ),
        migrations.CreateModel(
            name="VehicleModel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("display_order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "make",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="models",
                        to="vehicles.vehiclemake",
                    ),
                ),
            ],
            options={"ordering": ["display_order", "name"]},
        ),
        migrations.AddConstraint(
            model_name="vehiclemodel",
            constraint=models.UniqueConstraint(
                fields=("make", "name"),
                name="unique_vehicle_model_per_make",
            ),
        ),
        migrations.RunPython(seed_catalog, reverse_code=unseed_catalog),
    ]
