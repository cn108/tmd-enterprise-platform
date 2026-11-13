from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.parties.models import (
    Address,
    BankAccount,
    BankAccountChangeRequest,
    ComplianceDocument,
    Contact,
    Party,
    SupplierCategory,
    TaxRegistration,
)
from apps.parties.serializers import (
    AddressSerializer,
    BankAccountChangeRequestSerializer,
    BankAccountDecisionSerializer,
    BankAccountSerializer,
    ComplianceDocumentSerializer,
    ContactSerializer,
    CustomerSerializer,
    PartyOptionSerializer,
    SupplierCategorySerializer,
    SupplierSerializer,
    TaxRegistrationSerializer,
)
from shared.exceptions import error_response
from shared.permissions import ModelPermission
from shared.viewsets import ProtectedMasterDataViewSet, ProtectedNoDeleteViewSet

audit_logger = logging.getLogger("apps.parties.audit")
APPROVE_PERMISSION = "parties.approve_bankaccountchange"


class SupplierCategoryViewSet(ProtectedMasterDataViewSet):
    queryset = SupplierCategory.objects.all()
    serializer_class = SupplierCategorySerializer
    search_fields = ("code", "name")


class SupplierViewSet(ProtectedMasterDataViewSet):
    queryset = (
        Party.objects.filter(is_supplier=True)
        .select_related("supplier_category")
        .prefetch_related("tax_registrations", "addresses")
    )
    serializer_class = SupplierSerializer
    search_fields = ("code", "legal_name", "trading_name", "email")


class CustomerViewSet(ProtectedMasterDataViewSet):
    queryset = Party.objects.filter(is_customer=True).prefetch_related("addresses")
    serializer_class = CustomerSerializer
    search_fields = ("code", "legal_name", "trading_name", "email")

    def get_queryset(self):
        queryset = super().get_queryset()
        credit_hold = (self.request.query_params.get("credit_hold") or "").lower()
        if credit_hold in {"true", "false"}:
            queryset = queryset.filter(credit_hold=credit_hold == "true")
        return queryset


class PartyViewSet(viewsets.ReadOnlyModelViewSet):
    """Every party, for contacts, addresses and tax registrations."""

    queryset = Party.objects.all()
    serializer_class = PartyOptionSerializer
    permission_classes = [ModelPermission]
    search_fields = ("code", "legal_name", "trading_name")
    ordering_fields = ("code", "legal_name")

    def get_queryset(self):
        queryset = super().get_queryset()
        role = (self.request.query_params.get("role") or "").strip()
        if role == "supplier":
            queryset = queryset.filter(is_supplier=True)
        elif role == "customer":
            queryset = queryset.filter(is_customer=True)
        return queryset


class ContactViewSet(ProtectedNoDeleteViewSet):
    queryset = Contact.objects.select_related("party").all()
    serializer_class = ContactSerializer
    search_fields = ("party__code", "name", "role", "email")


class AddressViewSet(ProtectedNoDeleteViewSet):
    queryset = Address.objects.select_related("party").all()
    serializer_class = AddressSerializer
    search_fields = ("party__code", "label", "line1", "city", "state")


class TaxRegistrationViewSet(ProtectedNoDeleteViewSet):
    queryset = TaxRegistration.objects.select_related("party").all()
    serializer_class = TaxRegistrationSerializer
    search_fields = ("party__code", "scheme", "number")


class BankAccountViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only: accounts change only through an approved request (B-27)."""

    queryset = BankAccount.objects.select_related("supplier").all()
    serializer_class = BankAccountSerializer
    permission_classes = [ModelPermission]
    search_fields = ("supplier__code", "bank_name", "account_name", "account_last4")


class BankAccountChangeRequestViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = BankAccountChangeRequest.objects.select_related(
        "supplier", "bank_account", "created_by", "reviewed_by"
    )
    serializer_class = BankAccountChangeRequestSerializer
    permission_classes = [ModelPermission]
    search_fields = (
        "supplier__code",
        "proposed_bank_name",
        "proposed_account_name",
        "status",
    )

    def get_queryset(self):
        queryset = super().get_queryset()
        status_filter = (self.request.query_params.get("status") or "").strip()
        if status_filter in BankAccountChangeRequest.Status.values:
            queryset = queryset.filter(status=status_filter)
        if self.request.user.has_perm(APPROVE_PERMISSION):
            return queryset
        return queryset.filter(created_by=self.request.user)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def _decide(self, request, pk, *, approve: bool):
        if not request.user.has_perm(APPROVE_PERMISSION):
            raise PermissionDenied("You are not allowed to review bank account changes.")

        decision = BankAccountDecisionSerializer(data=request.data)
        decision.is_valid(raise_exception=True)
        note = decision.validated_data.get("review_note", "")

        with transaction.atomic():
            # Lock the request row only: ``bank_account`` is nullable, and
            # PostgreSQL cannot lock the nullable side of an outer join.
            change = (
                BankAccountChangeRequest.objects.select_for_update()
                .select_related("supplier")
                .filter(pk=pk)
                .first()
            )
            if change is None:
                return error_response(
                    "not_found", "No such change request.", status.HTTP_404_NOT_FOUND
                )
            if change.created_by_id == request.user.pk:
                return error_response(
                    "self_approval",
                    "You cannot review your own bank account change.",
                    status.HTTP_403_FORBIDDEN,
                )
            if change.status != BankAccountChangeRequest.Status.PENDING:
                return error_response(
                    "invalid_state",
                    "This change request has already been reviewed.",
                    status.HTTP_409_CONFLICT,
                )

            account = change.apply_proposed_changes() if approve else None
            change.status = (
                BankAccountChangeRequest.Status.APPROVED
                if approve
                else BankAccountChangeRequest.Status.REJECTED
            )
            change.reviewed_by = request.user
            change.reviewed_at = timezone.now()
            change.review_note = note
            change.updated_by = request.user
            change.save()

        # Application-log record until the append-only audit trail (W7) exists.
        # It deliberately contains no account number or ciphertext.
        audit_logger.info(
            "bank_account_change.%s" % ("approved" if approve else "rejected"),
            extra={
                "change_request_id": change.pk,
                "bank_account_id": account.pk if account else change.bank_account_id,
                "supplier_id": change.supplier_id,
                "actor_id": request.user.pk,
            },
        )
        return Response(BankAccountChangeRequestSerializer(change).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._decide(request, pk, approve=True)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._decide(request, pk, approve=False)


class ComplianceDocumentViewSet(ProtectedNoDeleteViewSet):
    queryset = ComplianceDocument.objects.select_related("supplier", "document").all()
    serializer_class = ComplianceDocumentSerializer
    search_fields = ("supplier__code", "document_type", "reference")
