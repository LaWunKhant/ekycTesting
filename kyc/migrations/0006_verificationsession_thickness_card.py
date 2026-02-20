from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("kyc", "0005_verificationsession_physical_card_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="verificationsession",
            name="thickness_card",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
