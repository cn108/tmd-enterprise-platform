"""Sequential document numbering, configured rather than hard-coded."""

from __future__ import annotations

from datetime import date

from django.db import transaction
from django.utils import timezone

from apps.core.models import NumberingScheme


class NumberingError(Exception):
    """The requested numbering scheme is missing or inactive."""


@transaction.atomic
def allocate_document_number(document_type: str, on_date: date | None = None) -> str:
    scheme = (
        NumberingScheme.objects.select_for_update()
        .filter(document_type=document_type, is_active=True)
        .first()
    )
    if scheme is None:
        raise NumberingError(f"No active numbering scheme for {document_type}.")
    target = on_date or timezone.localdate()
    if scheme.reset_yearly and scheme.last_allocated_year != target.year:
        scheme.next_value = 1
        scheme.last_allocated_year = target.year
    number = f"{scheme.prefix}-{target.year}-{scheme.next_value:0{scheme.padding}d}"
    scheme.next_value += 1
    scheme.save(update_fields=["next_value", "last_allocated_year", "updated_at"])
    return number
