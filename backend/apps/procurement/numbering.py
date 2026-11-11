"""Year-scoped document numbers (M-01)."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.procurement.models import DocumentSequence


def next_number(kind: str) -> str:
    year = timezone.now().year
    with transaction.atomic():
        sequence, _ = DocumentSequence.objects.select_for_update().get_or_create(
            kind=kind, year=year
        )
        sequence.last_number += 1
        sequence.save(update_fields=["last_number"])
    return f"{kind}-{year}-{sequence.last_number:04d}"
