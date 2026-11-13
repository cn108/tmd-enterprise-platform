"""Read-mostly governance endpoints and the configuration report."""

from __future__ import annotations

from django.contrib.auth.models import Group
from django.db.models import Count
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounting.models import (
    AccountingSettings,
    AccountRole,
    AccountRoleMapping,
    FinancialEvent,
    PostingRule,
)
from apps.core.approvals import creator_cannot_decide
from apps.core.models import (
    ApprovalPolicy,
    ApprovalRecord,
    AuditEvent,
    NumberingScheme,
    PolicyDecision,
    TaxConfiguration,
    TaxProfile,
    create_audit_event,
)
from apps.core.numbering import NumberingError, allocate_document_number
from apps.core.serializers import (
    ApprovalPolicySerializer,
    ApprovalRecordSerializer,
    AuditEventSerializer,
    NumberingSchemeSerializer,
    PolicyDecisionSerializer,
    TaxConfigurationSerializer,
    TaxProfileSerializer,
)
from shared.exceptions import error_response


def _require(request, permission: str) -> None:
    if not request.user.has_perm(permission):
        raise PermissionDenied("You do not have permission for this action.")


class PolicyDecisionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PolicyDecision.objects.all()
    serializer_class = PolicyDecisionSerializer


class ApprovalPolicyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ApprovalPolicy.objects.select_related("required_role").all()
    serializer_class = ApprovalPolicySerializer


class ApprovalRecordViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ApprovalRecord.objects.select_related("approver").all()
    serializer_class = ApprovalRecordSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        for param in ("document_type", "document_id", "decision"):
            value = (self.request.query_params.get(param) or "").strip()
            if value:
                queryset = queryset.filter(**{param: value})
        return queryset


class AuditEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditEvent.objects.select_related("actor").all()
    serializer_class = AuditEventSerializer
    search_fields = ("action", "entity_type", "entity_id")
    ordering_fields = ("id", "occurred_at")

    def list(self, request, *args, **kwargs):
        _require(request, "core.view_audit")
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        _require(request, "core.view_audit")
        return super().retrieve(request, *args, **kwargs)


class TaxConfigurationViewSet(viewsets.ModelViewSet):
    queryset = TaxConfiguration.objects.all()
    serializer_class = TaxConfigurationSerializer
    search_fields = ("code", "name")
    ordering_fields = ("code", "tax_type", "effective_from")

    def get_queryset(self):
        queryset = super().get_queryset()
        status = (self.request.query_params.get("review_status") or "").strip()
        if status in TaxConfiguration.ReviewStatus.values:
            queryset = queryset.filter(review_status=status)
        return queryset

    def create(self, request, *args, **kwargs):
        _require(request, "core.add_taxconfiguration")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, "core.change_taxconfiguration")
        instance = self.get_object()
        if instance.review_status == TaxConfiguration.ReviewStatus.REVIEWED:
            return error_response(
                "invalid_state",
                "A reviewed tax configuration is superseded by a new rate, not edited.",
                status.HTTP_409_CONFLICT,
            )
        return super().update(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        return error_response(
            "delete_not_permitted",
            "Tax configuration is deactivated, not deleted, so history stays explainable.",
            status.HTTP_409_CONFLICT,
        )

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        _require(request, "core.change_taxconfiguration")
        record = self.get_object()
        if record.review_status == TaxConfiguration.ReviewStatus.REVIEWED:
            return error_response(
                "invalid_state",
                "This tax configuration is already reviewed.",
                status.HTTP_409_CONFLICT,
            )
        if creator_cannot_decide(request.user, record.created_by_id):
            return error_response(
                "segregation_of_duties",
                "The person who created the tax configuration cannot review it.",
                status.HTTP_409_CONFLICT,
            )
        notes = str(request.data.get("notes", "")).strip()
        if not notes:
            return error_response(
                "notes_required",
                "Record the review rationale before approving a tax configuration.",
                status.HTTP_400_BAD_REQUEST,
            )
        before = {"review_status": record.review_status, "rate": str(record.rate)}
        record.review_status = TaxConfiguration.ReviewStatus.REVIEWED
        record.reviewed_by = request.user
        record.reviewed_at = timezone.now()
        record.updated_by = request.user
        record.notes = notes
        record.save()
        create_audit_event(
            actor=request.user,
            action="tax.reviewed",
            entity_type="TaxConfiguration",
            entity_id=record.pk,
            before=before,
            after={"review_status": record.review_status},
            metadata={"notes": notes},
            request=request,
        )
        return Response(TaxConfigurationSerializer(record).data)


class TaxProfileView(APIView):
    def get(self, request):
        profile = TaxProfile.objects.order_by("id").first()
        return Response(TaxProfileSerializer(profile).data if profile else None)

    def post(self, request):
        _require(request, "core.add_taxprofile")
        if TaxProfile.objects.exists():
            return error_response(
                "invalid_state", "A tax profile already exists.", status.HTTP_409_CONFLICT
            )
        serializer = TaxProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def patch(self, request):
        _require(request, "core.change_taxprofile")
        profile = TaxProfile.objects.order_by("id").first()
        if profile is None:
            return error_response("not_found", "No tax profile exists.", status.HTTP_404_NOT_FOUND)
        serializer = TaxProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class NumberingSchemeViewSet(viewsets.ModelViewSet):
    queryset = NumberingScheme.objects.all()
    serializer_class = NumberingSchemeSerializer
    search_fields = ("document_type", "prefix")

    def create(self, request, *args, **kwargs):
        _require(request, "core.add_numberingscheme")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, "core.change_numberingscheme")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        return error_response(
            "delete_not_permitted",
            "Numbering schemes are deactivated, not deleted.",
            status.HTTP_409_CONFLICT,
        )

    @action(detail=True, methods=["post"])
    def next(self, request, pk=None):
        _require(request, "core.change_numberingscheme")
        scheme = self.get_object()
        try:
            number = allocate_document_number(scheme.document_type)
        except NumberingError as exc:
            return error_response("invalid_state", str(exc), status.HTTP_409_CONFLICT)
        create_audit_event(
            actor=request.user,
            action="numbering.allocated",
            entity_type="NumberingScheme",
            entity_id=scheme.pk,
            after={"number": number},
            metadata={"document_type": scheme.document_type},
            request=request,
        )
        return Response({"document_type": scheme.document_type, "number": number})


class ConfigurationReportView(APIView):
    """The report required by the provisional-policy instruction."""

    def get(self, request):
        roles = list(Group.objects.order_by("name").values_list("name", flat=True))
        account_roles = AccountRole.objects.count()
        approved_mappings = AccountRoleMapping.objects.filter(
            approved_at__isnull=False, is_active=True
        ).count()
        rules = PostingRule.objects.all()
        approved_rules = rules.filter(approved_at__isnull=False, is_active=True).count()
        events = FinancialEvent.objects.values("status").order_by()
        event_counts = {row["status"]: row["count"] for row in events.annotate(count=Count("id"))}
        policies = PolicyDecision.objects.filter(status=PolicyDecision.Status.PROVISIONAL)
        tax = TaxConfiguration.objects.all()
        reviewed_tax = tax.filter(review_status=TaxConfiguration.ReviewStatus.REVIEWED).count()
        numbering = NumberingScheme.objects.all()
        settings = AccountingSettings.objects.filter(pk=1).first()
        review_recorded = bool(settings and settings.posting_reviewed_at)
        outstanding = [
            "The nine operational roles plus the unassigned Finance Controller are provisional "
            "and have no named role holders.",
            "No account has been created or approved, so no role mapping is complete.",
            f"{account_roles - approved_mappings} account roles still need an approved mapping.",
            f"{rules.count() - approved_rules} posting rules remain unapproved.",
            "No opening balances, bank balances, tax liabilities or tax rates have been entered.",
            "No users have been assigned to the nine roles.",
        ]
        if not review_recorded:
            outstanding.append("No Finance Controller review has been recorded.")
        posting_enabled = (
            review_recorded
            and approved_rules == rules.count()
            and approved_mappings >= account_roles
        )

        return Response(
            {
                "generated_at": timezone.now().isoformat(),
                "policy_version": "1.0-provisional",
                "effective_from": "2026-11-12",
                "implemented": [
                    {
                        "decision": "D-03",
                        "description": "Nine operational roles plus unassigned Finance Controller",
                        "roles": roles,
                    },
                    {
                        "decision": "D-04",
                        "description": "₦5,000,000 provisional approval threshold",
                        "bands": ApprovalPolicySerializer(
                            ApprovalPolicy.objects.all(), many=True
                        ).data,
                    },
                    {
                        "decision": "D-05",
                        "description": "Configurable account-role mappings",
                        "account_roles": account_roles,
                        "approved_mappings": approved_mappings,
                    },
                    {
                        "decision": "D-06",
                        "description": (
                            "Weighted average for ordinary stock; specific identification for "
                            "traceable items"
                        ),
                        "traceable_rule": "items with batch or serial tracking",
                    },
                    {
                        "decision": "P-06",
                        "description": "GRNI accrual event E-02",
                        "rule": "e02_grn_accrual",
                    },
                    {
                        "decision": "E-02 / E-04 / E-16",
                        "description": "Financial event outbox",
                        "events": event_counts,
                    },
                    {
                        "decision": "E-21",
                        "description": (
                            "Opening balances post through the controlled opening-balance document"
                        ),
                    },
                    {
                        "decision": "E-22",
                        "description": "Controlled period reopen plus reasoned adjustment journal",
                    },
                    {
                        "decision": "TAX-01",
                        "description": "Configurable VAT, WHT, Tax ID and NRS settings",
                        "tax_rules": tax.count(),
                        "reviewed_tax_rules": reviewed_tax,
                    },
                    {
                        "decision": "AUD-01",
                        "description": "Immutable journals, stock movements and audit events",
                    },
                ],
                "outstanding_controls": outstanding,
                "blocked_features": [
                    "Automatic financial posting remains pending until every event rule has "
                    "approved role mappings.",
                    "Invoice issuance, payment approval and NRS submission are not implemented "
                    "in Phase 6.",
                    "Tax returns are not filed and statutory approval is not claimed.",
                    "Production posting is disabled until a qualified Finance Controller reviews "
                    "the mappings and opening balances.",
                ],
                "assumptions_requiring_professional_review": [
                    "The ₦5,000,000 band means one approval below and two independent approvals "
                    "at or above the threshold.",
                    "HSE duties are folded into Operations / HSE; Requester is not a role because "
                    "all authenticated staff can raise requests.",
                    "Traceability is inferred from the item's batch or serial tracking flag.",
                    "The customer invoice numbering format is provisional and no invoice module "
                    "exists yet.",
                ],
                "configuration": {
                    "policies_provisional": policies.count(),
                    "financial_events": event_counts,
                    "numbering_schemes": NumberingSchemeSerializer(numbering, many=True).data,
                    "production_posting_enabled": posting_enabled,
                },
            }
        )
