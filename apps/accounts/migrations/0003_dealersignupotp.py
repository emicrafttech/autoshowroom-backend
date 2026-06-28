import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_alter_staffuser_groups_alter_staffuser_is_superuser"),
    ]

    operations = [
        migrations.CreateModel(
            name="DealerSignupOtp",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("phone", models.CharField(max_length=32)),
                ("code", models.CharField(max_length=8)),
                ("expires_at", models.DateTimeField()),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [models.Index(fields=["phone", "code"], name="accounts_de_phone_1afea2_idx")],
            },
        ),
    ]
