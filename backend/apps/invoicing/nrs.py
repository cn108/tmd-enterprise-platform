"""NRS e-invoicing adapter boundary.

The real adapter is intentionally not implemented: onboarding, credentials,
endpoint and API version are not supplied. The feature flag off is the default,
and no test replaces the adapter with a fake successful network call.
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.invoicing.models import CustomerInvoice, InvoiceSettings


@dataclass(frozen=True)
class NrsResult:
    status: str
    message: str
    response: dict


class NrsAdapter:
    """Interface a reviewed NRS integration must implement."""

    def submit(self, invoice: CustomerInvoice) -> NrsResult:
        raise NotImplementedError


class DisabledNrsAdapter(NrsAdapter):
    def submit(self, invoice: CustomerInvoice) -> NrsResult:
        return NrsResult(
            status="disabled",
            message="NRS integration is disabled by the feature flag.",
            response={},
        )


class UnconfiguredNrsAdapter(NrsAdapter):
    def submit(self, invoice: CustomerInvoice) -> NrsResult:
        return NrsResult(
            status="queued",
            message="NRS adapter endpoint is not configured; no network submission was attempted.",
            response={},
        )


def get_adapter(settings: InvoiceSettings) -> NrsAdapter:
    if not settings.nrs_enabled:
        return DisabledNrsAdapter()
    return UnconfiguredNrsAdapter()


def build_payload(invoice: CustomerInvoice) -> dict:
    return {
        "invoice_number": invoice.number,
        "invoice_date": invoice.invoice_date.isoformat(),
        "customer": invoice.customer.legal_name,
        "currency": invoice.currency,
        "subtotal": str(invoice.subtotal),
        "vat": str(invoice.vat_total),
        "total": str(invoice.total),
        "is_test": invoice.is_test,
    }
