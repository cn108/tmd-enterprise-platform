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
    SupplierCategorySerializer,
    SupplierSerializer,
    TaxRegistrationSerializer,
)
from shared.exceptions import error_response
from shared.viewsets import MasterDataViewSet, NoDeleteViewSet

audit_logger = logging.getLogger("apps.parties.audit")
APPROVE_PERMISSION = "parties.approve_bankaccountchange"


class SupplierCategoryViewSet(MasterDataViewSet):
    queryset = SupplierCategory.objects.all()
    serializer_class = SupplierCategorySerializer
    search_fields = ("code", "name")


class SupplierViewSet(MasterDataViewSet):
    queryset = Party.objects.filter(is_supplier=True).select_related("supplier_category")
    serializer_class = SupplierSerializer
    search_fields = ("code", "legal_name", "trading_name", "email")


class CustomerViewSet(MasterDataViewSet):
    queryset = Party.objects.filter(is_customer=True)
    serializer_class = CustomerSerializer
    search_fields = ("code", "legal_name", "trading_name", "email")


class ContactViewSet(NoDeleteViewSet):
    queryset = Contact.objects.select_related("party").all()
    serializer_class = ContactSerializer


class AddressViewSet(NoDeleteViewSet):
    queryset = Address.objects.select_related("party").all()
    serializer_class = AddressSerializer


class TaxRegistrationViewSet(NoDeleteViewSet):
    queryset = TaxRegistration.objects.select_related("party").all()
    serializer_class = TaxRegistrationSerializer


class BankAccountViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only: accounts change only through an approved request (B-27)."""

    queryset = BankAccount.objects.select_related("supplier").all()
    serializer_class = BankAccountSerializer


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

    def get_queryset(self):
        queryset = super().get_queryset()
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


class ComplianceDocumentViewSet(NoDeleteViewSet):
    queryset = ComplianceDocument.objects.select_related("supplier", "document").all()
    serializer_class = ComplianceDocumentSerializer
