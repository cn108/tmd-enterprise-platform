from __future__ import annotations

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def encrypt_existing_numbers(apps, schema_editor):
    """Encrypt any plaintext account numbers already stored (B-26)."""
    from apps.parties.crypto import encrypt_account_number

    BankAccount = apps.get_model("parties", "BankAccount")
    for account in BankAccount.objects.exclude(account_number="").iterator():
        raw = account.account_number
        account.account_number_encrypted = encrypt_account_number(raw)
        account.account_last4 = raw[-4:]
        account.save(update_fields=["account_number_encrypted", "account_last4"])


def decrypt_existing_numbers(apps, schema_editor):
    """Restore plaintext on reverse so a rollback is not lossy."""
    from apps.parties.crypto import decrypt_account_number

    BankAccount = apps.get_model("parties", "BankAccount")
    for account in BankAccount.objects.exclude(account_number_encrypted="").iterator():
        account.account_number = decrypt_account_number(account.account_number_encrypted)[:34]
        account.save(update_fields=["account_number"])


class Migration(migrations.Migration):
    dependencies = [
        ("parties", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BankAccountChangeRequest",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("proposed_bank_name", models.CharField(max_length=120)),
                ("proposed_account_name", models.CharField(max_length=150)),
                ("proposed_account_number_encrypted", models.TextField()),
                ("proposed_account_last4", models.CharField(max_length=4)),
                ("proposed_sort_code", models.CharField(blank=True, max_length=20)),
                ("proposed_currency", models.CharField(default="NGN", max_length=3)),
                ("reason", models.CharField(max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending approval"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                        ],
                        default="pending",
                        max_length=12,
                    ),
                ),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("review_note", models.CharField(blank=True, max_length=255)),
                (
                    "bank_account",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="change_requests",
                        to="parties.bankaccount",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "supplier",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="bank_change_requests",
                        to="parties.party",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "bank account change request",
                "verbose_name_plural": "bank account change requests",
                "ordering": ["-created_at"],
                "permissions": [
                    ("approve_bankaccountchange", "Can approve supplier bank account changes")
                ],
            },
        ),
        migrations.AddField(
            model_name="bankaccount",
            name="account_last4",
            field=models.CharField(default="", max_length=4),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="bankaccount",
            name="account_number_encrypted",
            field=models.TextField(default=""),
            preserve_default=False,
        ),
        migrations.RunPython(encrypt_existing_numbers, decrypt_existing_numbers),
        migrations.RemoveField(
            model_name="bankaccount",
            name="account_number",
        ),
    ]
