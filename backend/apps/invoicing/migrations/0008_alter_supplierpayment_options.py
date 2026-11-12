from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("invoicing", "0007_company_email_owner"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="supplierpayment",
            options={
                "ordering": ["-payment_date", "-id"],
                "permissions": [
                    ("approve_payment", "Can approve a supplier payment"),
                    ("record_payment", "Can record an externally executed payment"),
                    ("allocate_payment", "Can allocate a payment to invoices"),
                    (
                        "post_supplierpayment",
                        "Can post a recorded supplier payment to the ledger",
                    ),
                ],
            },
        ),
    ]
