from __future__ import annotations

from rest_framework import serializers

from apps.warehousing.models import StorageLocation, Warehouse
from shared.serializers import CodedSerializerMixin


class WarehouseSerializer(CodedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = [
            "id",
            "code",
            "name",
            "site_name",
            "address",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class StorageLocationSerializer(CodedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = StorageLocation
        fields = [
            "id",
            "warehouse",
            "code",
            "name",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]
