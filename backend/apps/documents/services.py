"""Shared secure document attachment workflow."""

from __future__ import annotations

from rest_framework import serializers

from apps.core.models import create_audit_event
from apps.documents.models import DocumentLink
from apps.documents.serializers import DocumentSerializer


def attach_upload(
    *,
    upload,
    title: str,
    entity_type: str,
    entity_id: int,
    user,
    request=None,
    category=None,
    notes: str = "",
) -> tuple:
    """Store a private document and link it to one business record.

    The file is validated by the same serializer used by the document API, so
    extension, size and checksum rules are identical on every upload path. The
    document bytes remain immutable and downloads stay authenticated.
    """
    if upload is None:
        raise serializers.ValidationError({"file": "Choose a file to attach."})
    serializer = DocumentSerializer(
        data={
            "title": (title or "").strip() or upload.name,
            "file": upload,
            "category": category.pk if category is not None else None,
            "is_private": True,
            "notes": notes,
        }
    )
    serializer.is_valid(raise_exception=True)
    document = serializer.save(created_by=user, updated_by=user)
    link, created = DocumentLink.objects.get_or_create(
        document=document,
        entity_type=entity_type,
        entity_id=entity_id,
        defaults={"created_by": user, "updated_by": user},
    )
    if not created:
        link.updated_by = user
        link.save(update_fields=["updated_by", "updated_at"])
    create_audit_event(
        actor=user,
        action="document.attached",
        entity_type=f"documents.{entity_type}",
        entity_id=entity_id,
        after={
            "document": document.pk,
            "filename": document.original_filename,
            "link": link.pk,
        },
        request=request,
    )
    return document, link
