from __future__ import annotations

import hashlib
from pathlib import Path

from django.conf import settings
from rest_framework import serializers

from apps.documents.models import Document, DocumentCategory, DocumentLink
from shared.serializers import CodedSerializerMixin


class DocumentCategorySerializer(CodedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = DocumentCategory
        fields = [
            "id",
            "code",
            "name",
            "retention_months",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class DocumentSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True, required=False)

    class Meta:
        model = Document
        fields = [
            "id",
            "category",
            "title",
            "file",
            "original_filename",
            "mime_type",
            "size_bytes",
            "checksum_sha256",
            "version",
            "supersedes",
            "is_private",
            "retention_until",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "original_filename",
            "mime_type",
            "size_bytes",
            "checksum_sha256",
            "created_at",
            "updated_at",
        ]

    def validate_file(self, upload):
        extension = Path(upload.name).suffix.lower()
        allowed = {item.strip().lower() for item in settings.DOCUMENT_ALLOWED_EXTENSIONS}
        if extension not in allowed:
            raise serializers.ValidationError(
                f"Files of type {extension or 'unknown'} are not accepted. "
                f"Allowed: {', '.join(sorted(allowed))}."
            )
        if upload.size > settings.DOCUMENT_MAX_UPLOAD_BYTES:
            raise serializers.ValidationError(
                f"The file exceeds the {settings.DOCUMENT_MAX_UPLOAD_BYTES} byte limit."
            )
        return upload

    def validate(self, attrs):
        if self.instance is None and not attrs.get("file"):
            raise serializers.ValidationError({"file": "A file is required."})
        return attrs

    def create(self, validated_data):
        upload = validated_data.get("file")
        if upload:
            digest = hashlib.sha256()
            for chunk in upload.chunks():
                digest.update(chunk)
            upload.seek(0)
            validated_data["checksum_sha256"] = digest.hexdigest()
            validated_data["size_bytes"] = upload.size
            validated_data["original_filename"] = Path(upload.name).name
            validated_data["mime_type"] = getattr(upload, "content_type", "") or ""
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # A document's bytes are immutable; a new version supersedes the old one.
        validated_data.pop("file", None)
        return super().update(instance, validated_data)


class DocumentLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentLink
        fields = [
            "id",
            "document",
            "entity_type",
            "entity_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]
