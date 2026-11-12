from django.db import migrations

OLD_EMAIL = "tmdtico@gmail.com"
NEW_EMAIL = "ccmtico1234@gmail.com"


def update_company_email(apps, schema_editor):
    InvoiceSettings = apps.get_model("invoicing", "InvoiceSettings")
    InvoiceSettings.objects.filter(company_email=OLD_EMAIL).update(company_email=NEW_EMAIL)


class Migration(migrations.Migration):
    dependencies = [
        ("invoicing", "0006_company_email"),
    ]

    operations = [
        migrations.RunPython(update_company_email, migrations.RunPython.noop),
    ]