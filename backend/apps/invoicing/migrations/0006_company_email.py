from django.db import migrations

COMPANY_EMAIL = "tmdtico@gmail.com"


def set_company_email(apps, schema_editor):
    InvoiceSettings = apps.get_model("invoicing", "InvoiceSettings")
    for settings in InvoiceSettings.objects.all():
        if not settings.company_email.strip() or settings.company_email.lower().endswith(
            "@staging.tmd.local"
        ):
            settings.company_email = COMPANY_EMAIL
            settings.save(update_fields=["company_email"])


class Migration(migrations.Migration):
    dependencies = [("invoicing", "0005_alter_customerinvoice_options_and_more")]

    operations = [migrations.RunPython(set_company_email, migrations.RunPython.noop)]
