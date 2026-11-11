from __future__ import annotations

from rest_framework import serializers

from apps.organisation.models import CostCentre, Department
from shared.serializers import CodedSerializerMixin


class DepartmentSerializer(CodedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = [
            "id",
            "code",
            "name",
            "parent",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class CostCentreSerializer(CodedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = CostCentre
        fields = [
            "id",
            "code",
            "name",
            "parent",
            "department",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_parent(self, value):
        if self.instance and value:
            if value.pk == self.instance.pk:
                raise serializers.ValidationError("A cost centre cannot be its own parent.")
            ancestor = value
            seen: set[int] = set()
            while ancestor is not None:
                if ancestor.pk in seen:
                    break
                if ancestor.pk == self.instance.pk:
                    raise serializers.ValidationError("Cost centres cannot form a cycle.")
                seen.add(ancestor.pk)
                ancestor = ancestor.parent
        return value
