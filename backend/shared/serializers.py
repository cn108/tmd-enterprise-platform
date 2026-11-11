"""Shared serializer behaviour for coded master data."""

from __future__ import annotations


class CodedSerializerMixin:
    """Normalises ``code`` before DRF's uniqueness validator sees it.

    Models upper-case codes in ``save()``, which is too late: a duplicate
    submitted as ``dup-1`` would pass the uniqueness check and then hit the
    database constraint as a 500. Normalising the incoming value keeps the
    duplicate a normal 400 field error.
    """

    def to_internal_value(self, data):
        try:
            raw = data.get("code")
        except AttributeError:
            raw = None
        if isinstance(raw, str):
            data = data.copy()
            data["code"] = raw.strip().upper()
        return super().to_internal_value(data)
