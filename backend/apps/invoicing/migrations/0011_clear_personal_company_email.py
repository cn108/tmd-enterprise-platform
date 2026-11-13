"""Remove the former personal Gmail address from invoice settings.

Production must use a company-controlled mailbox. The historical migration is
left intact; this forward migration clears only the exact old value.
"""

from django.db import migrations

PERSONAL_EMAIL = "ccmtico1234@gmail.com"


def clear_personal_email(apps, schema_editor):
    InvoiceSettings = apps.get_model("invoicing", "InvoiceSettings")
    InvoiceSettings.objects.filter(company_email=PERSONAL_EMAIL).update(company_email="")


class Migration(migrations.Migration):
    dependencies = [("invoicing", "0010_alter_customerreceipt_options_and_more")]

    operations = [
        migrations.RunPython(clear_personal_email, migrations.RunPython.noop),
    ]
