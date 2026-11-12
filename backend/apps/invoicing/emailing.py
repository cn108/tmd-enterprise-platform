"""Send an approved invoice PDF from the configured company mailbox.

The PDF is generated on demand and attached; no copy is persisted.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email

from apps.core.models import create_audit_event
from apps.invoicing.models import CustomerInvoice, InvoiceSettings, SupplierInvoice
from apps.invoicing.pdf import customer_invoice_pdf_bytes, supplier_invoice_pdf_bytes

logger = logging.getLogger(__name__)


class InvoiceEmailError(Exception):
    """A user-correctable reason the invoice was not emailed."""


class InvoiceEmailDeliveryError(InvoiceEmailError):
    """The configured mail provider failed to accept the message."""


def _address(value: str, field: str) -> str:
    address = (value or "").strip()
    try:
        validate_email(address)
    except ValidationError as exc:
        raise InvoiceEmailError(f"Enter a valid {field} address.") from exc
    return address


def _cc_addresses(value: str) -> list[str]:
    addresses = [
        part.strip()
        for part in (value or "").replace(";", ",").split(",")
        if part.strip()
    ]
    return [_address(address, "CC") for address in addresses]


def _send(
    invoice,
    pdf: bytes,
    party_name: str,
    recipient: str,
    cc: str,
    message: str,
    actor,
    *,
    request=None,
) -> dict:
    invoice_settings = InvoiceSettings.load()
    expected = (
        SupplierInvoice.Status.APPROVED
        if isinstance(invoice, SupplierInvoice)
        else CustomerInvoice.Status.APPROVED
    )
    if invoice.status != expected:
        raise InvoiceEmailError("Only an approved invoice can be emailed.")

    to = _address(recipient, "recipient")
    cc_addresses = _cc_addresses(cc)
    company = invoice_settings.company_legal_name.strip() or "Tico McDon Limited"
    subject = f"Invoice {invoice.number} from {company}"
    body = (message or "").strip()
    if not body:
        body = (
            f"Dear {party_name},\n\n"
            f"Please find attached invoice {invoice.number} for "
            f"{invoice.currency} {invoice.total}.\n\n"
            f"Regards,\n{company}"
        )

    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to],
        cc=cc_addresses,
        reply_to=[invoice_settings.company_email]
        if invoice_settings.company_email.strip()
        else None,
    )
    email.attach(f"{invoice.number}.pdf", pdf, "application/pdf")

    try:
        sent = email.send(fail_silently=False)
    except Exception as exc:  # noqa: BLE001 - the provider may raise many socket/SSL errors
        logger.exception("Invoice email delivery failed for %s", invoice.number)
        raise InvoiceEmailDeliveryError(
            "The email could not be delivered. Check the company mailbox configuration "
            "and try again."
        ) from exc
    if sent != 1:
        raise InvoiceEmailDeliveryError("The email provider did not accept the message.")

    kind = "supplier" if isinstance(invoice, SupplierInvoice) else "customer"
    create_audit_event(
        actor=actor,
        action=f"{kind}_invoice.emailed",
        entity_type=(
            "invoicing.supplierinvoice"
            if isinstance(invoice, SupplierInvoice)
            else "invoicing.customerinvoice"
        ),
        entity_id=invoice.pk,
        after={"number": invoice.number, "to": to, "cc": cc_addresses, "subject": subject},
        request=request,
    )
    return {
        "detail": f"{invoice.number} emailed to {to}.",
        "number": invoice.number,
        "to": to,
        "cc": cc_addresses,
    }


def send_supplier_invoice_email(
    invoice: SupplierInvoice,
    recipient: str,
    cc: str = "",
    message: str = "",
    actor=None,
    *,
    request=None,
) -> dict:
    return _send(
        invoice,
        supplier_invoice_pdf_bytes(invoice),
        invoice.supplier.legal_name,
        recipient,
        cc,
        message,
        actor,
        request=request,
    )


def send_customer_invoice_email(
    invoice: CustomerInvoice,
    recipient: str,
    cc: str = "",
    message: str = "",
    actor=None,
    *,
    request=None,
) -> dict:
    return _send(
        invoice,
        customer_invoice_pdf_bytes(invoice),
        invoice.customer.legal_name,
        recipient,
        cc,
        message,
        actor,
        request=request,
    )
