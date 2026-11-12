from __future__ import annotations

from pathlib import Path

from django.http import FileResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.banking.models import (
    BankAccount,
    BankingSettings,
    BankStatement,
    BankTransaction,
    BankTransfer,
    CashAccount,
    CashVoucher,
    PettyCashReplenishment,
    Reconciliation,
    ReconciliationMatch,
    StatementLine,
)
from apps.banking.serializers import (
    BankAccountSerializer,
    BankingSettingsSerializer,
    BankStatementSerializer,
    BankTransactionSerializer,
    BankTransferSerializer,
    CashAccountSerializer,
    CashVoucherSerializer,
    PettyCashReplenishmentSerializer,
    ReconciliationSerializer,
    StatementLineSerializer,
)
from apps.banking.services import (
    BankingConflict,
    account_summary,
    approve_reconciliation,
    exclude_line,
    import_statement,
    match_statement_line,
    record_cash_voucher,
    record_replenishment,
    record_transfer,
    reject_reconciliation,
    report_rows,
    submit_reconciliation,
    suggestions_for_line,
    unmatch,
)
from apps.core.models import create_audit_event
from apps.procurement.numbering import next_number
from shared.exceptions import error_response
from shared.viewsets import MasterDataViewSet, NoDeleteViewSet


def _require(request, permission: str) -> None:
    if not request.user.has_perm(permission):
        raise PermissionDenied("You do not have permission for this action.")


def _conflict(exc: BankingConflict) -> Response:
    return error_response("invalid_state", str(exc), status.HTTP_409_CONFLICT)


class BankingViewPermissionMixin:
    view_permission = ""

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method in SAFE_METHODS and self.view_permission:
            _require(request, self.view_permission)


def _audit(request, action_name: str, entity_type: str, entity_id: int, after: dict) -> None:
    create_audit_event(
        actor=request.user,
        action=action_name,
        entity_type=entity_type,
        entity_id=entity_id,
        after=after,
        request=request,
    )


class BankAccountViewSet(BankingViewPermissionMixin, MasterDataViewSet):
    view_permission = "banking.view_bankaccount"
    queryset = BankAccount.objects.select_related("gl_account").all()
    serializer_class = BankAccountSerializer
    search_fields = ("code", "name", "bank_name", "last4")

    def create(self, request, *args, **kwargs):
        _require(request, "banking.manage_bankaccounts")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, "banking.manage_bankaccounts")
        return super().update(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        _audit(
            self.request,
            "bank_account.created",
            "banking.bankaccount",
            serializer.instance.pk,
            {"code": serializer.instance.code},
        )

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        return Response(account_summary(self.get_object()))


class BankingSettingsView(APIView):
    def get(self, request):
        _require(request, "banking.view_bankingsettings")
        return Response(BankingSettingsSerializer(BankingSettings.load()).data)

    def patch(self, request):
        _require(request, "banking.manage_bankingsettings")
        record = BankingSettings.load()
        serializer = BankingSettingsSerializer(record, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        _audit(
            request,
            "banking_settings.updated",
            "banking.bankingsettings",
            record.pk,
            serializer.data,
        )
        return Response(serializer.data)


class BankStatementViewSet(BankingViewPermissionMixin, viewsets.ReadOnlyModelViewSet):
    view_permission = "banking.view_bankstatement"
    queryset = BankStatement.objects.select_related("bank_account", "imported_by").all()
    serializer_class = BankStatementSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    search_fields = ("number", "reference", "bank_account__code", "original_filename")

    def get_queryset(self):
        queryset = super().get_queryset()
        for name in ("bank_account", "status"):
            value = (self.request.query_params.get(name) or "").strip()
            if value:
                queryset = queryset.filter(**{name: value})
        return queryset

    def create(self, request, *args, **kwargs):
        _require(request, "banking.import_bankstatement")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data.pop("source_file")
        mapping = serializer.validated_data.pop("column_mapping", None)
        try:
            statement = import_statement(
                bank_account=serializer.validated_data["bank_account"],
                upload=upload,
                user=request.user,
                validated={**serializer.validated_data, "column_mapping": mapping or {}},
            )
        except BankingConflict as exc:
            return _conflict(exc)
        return Response(BankStatementSerializer(statement).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        statement = self.get_object()
        if not statement.source_file:
            return error_response(
                "not_found", "No source file was stored.", status.HTTP_404_NOT_FOUND
            )
        create_audit_event(
            actor=request.user,
            action="bank_statement.downloaded",
            entity_type="banking.bankstatement",
            entity_id=statement.pk,
            after={"filename": statement.original_filename},
            request=request,
        )
        return FileResponse(
            statement.source_file.open("rb"),
            as_attachment=True,
            filename=statement.original_filename or Path(statement.source_file.name).name,
        )


class StatementLineViewSet(BankingViewPermissionMixin, viewsets.ReadOnlyModelViewSet):
    view_permission = "banking.view_statementline"
    queryset = StatementLine.objects.select_related(
        "statement", "statement__bank_account", "duplicate_of"
    ).all()
    serializer_class = StatementLineSerializer
    search_fields = ("description", "reference", "external_id", "statement__number")

    def get_queryset(self):
        queryset = super().get_queryset()
        values = {
            "statement": self.request.query_params.get("statement"),
            "status": self.request.query_params.get("status"),
            "duplicate_status": self.request.query_params.get("duplicate_status"),
            "classification": self.request.query_params.get("classification"),
        }
        for name, value in values.items():
            if value:
                queryset = queryset.filter(**{name: value})
        account = self.request.query_params.get("bank_account")
        if account:
            queryset = queryset.filter(statement__bank_account_id=account)
        return queryset

    @action(detail=True, methods=["get"])
    def suggestions(self, request, pk=None):
        _require(request, "banking.match_banktransaction")
        return Response({"results": suggestions_for_line(self.get_object())})

    @action(detail=True, methods=["post"])
    def match(self, request, pk=None):
        _require(request, "banking.match_banktransaction")
        line = self.get_object()
        transaction_id = request.data.get("bank_transaction")
        if not transaction_id:
            return error_response(
                "invalid_request", "Choose a bank transaction.", status.HTTP_400_BAD_REQUEST
            )
        transaction = BankTransaction.objects.filter(pk=transaction_id).first()
        if transaction is None:
            return error_response(
                "not_found", "Unknown bank transaction.", status.HTTP_404_NOT_FOUND
            )
        reconciliation = getattr(line.statement, "reconciliation", None)
        if reconciliation is None:
            return error_response(
                "invalid_state",
                "This statement has no reconciliation workspace.",
                status.HTTP_409_CONFLICT,
            )
        amount = request.data.get("amount") or line.remaining_amount
        try:
            match_statement_line(
                line=line,
                reconciliation=reconciliation,
                transaction=transaction,
                amount=amount,
                match_type=request.data.get("match_type")
                or ReconciliationMatch.MatchType.ONE_TO_ONE,
                user=request.user,
                notes=(request.data.get("notes") or "").strip(),
            )
        except BankingConflict as exc:
            return _conflict(exc)
        return Response(ReconciliationSerializer(reconciliation).data)

    @action(detail=True, methods=["post"])
    def unmatch(self, request, pk=None):
        _require(request, "banking.match_banktransaction")
        line = self.get_object()
        match = line.matches.filter(status=ReconciliationMatch.Status.CONFIRMED).first()
        if match is None:
            return error_response(
                "invalid_state", "This line has no match.", status.HTTP_409_CONFLICT
            )
        try:
            unmatch(match, request.user)
        except BankingConflict as exc:
            return _conflict(exc)
        return Response(StatementLineSerializer(line).data)

    @action(detail=True, methods=["post"])
    def exclude(self, request, pk=None):
        _require(request, "banking.match_banktransaction")
        try:
            line = exclude_line(
                self.get_object(), request.user, (request.data.get("reason") or "").strip()
            )
        except BankingConflict as exc:
            return _conflict(exc)
        return Response(StatementLineSerializer(line).data)

    @action(detail=True, methods=["post"])
    def classify(self, request, pk=None):
        _require(request, "banking.match_banktransaction")
        line = self.get_object()
        classification = request.data.get("classification")
        if classification not in StatementLine.Classification.values:
            return error_response(
                "invalid_request",
                "Unknown statement-line classification.",
                status.HTTP_400_BAD_REQUEST,
            )
        line.classification = classification
        line.save(update_fields=["classification"])
        _audit(
            request,
            "statement_line.classified",
            "banking.statementline",
            line.pk,
            {"classification": classification},
        )
        return Response(StatementLineSerializer(line).data)


class BankTransactionViewSet(BankingViewPermissionMixin, NoDeleteViewSet):
    view_permission = "banking.view_banktransaction"
    queryset = BankTransaction.objects.select_related("bank_account").all()
    serializer_class = BankTransactionSerializer
    search_fields = ("number", "description", "reference", "bank_account__code")

    def get_queryset(self):
        queryset = super().get_queryset()
        for name in ("bank_account", "status", "source_type"):
            value = (self.request.query_params.get(name) or "").strip()
            if value:
                queryset = queryset.filter(**{name: value})
        return queryset

    def create(self, request, *args, **kwargs):
        _require(request, "banking.match_banktransaction")
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(
            number=next_number("BTX"),
            source_type=BankTransaction.Source.MANUAL,
            status=BankTransaction.Status.EXPECTED,
            created_by=self.request.user,
            updated_by=self.request.user,
        )


class ReconciliationViewSet(BankingViewPermissionMixin, viewsets.ReadOnlyModelViewSet):
    view_permission = "banking.view_reconciliation"
    queryset = (
        Reconciliation.objects.select_related(
            "bank_account", "statement", "prepared_by", "approved_by"
        )
        .prefetch_related("matches")
        .all()
    )
    serializer_class = ReconciliationSerializer
    search_fields = ("number", "bank_account__code", "statement__number")

    def get_queryset(self):
        queryset = super().get_queryset()
        for name in ("bank_account", "status"):
            value = (self.request.query_params.get(name) or "").strip()
            if value:
                queryset = queryset.filter(**{name: value})
        return queryset

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        _require(request, "banking.submit_reconciliation")
        try:
            reconciliation = submit_reconciliation(self.get_object(), request.user)
        except BankingConflict as exc:
            return _conflict(exc)
        return Response(ReconciliationSerializer(reconciliation).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        _require(request, "banking.approve_reconciliation")
        try:
            reconciliation = approve_reconciliation(self.get_object(), request.user)
        except BankingConflict as exc:
            return _conflict(exc)
        return Response(ReconciliationSerializer(reconciliation).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        _require(request, "banking.approve_reconciliation")
        try:
            reconciliation = reject_reconciliation(
                self.get_object(), request.user, (request.data.get("reason") or "").strip()
            )
        except BankingConflict as exc:
            return _conflict(exc)
        return Response(ReconciliationSerializer(reconciliation).data)

    @action(detail=True, methods=["get"])
    def report(self, request, pk=None):
        reconciliation = self.get_object()
        return Response(
            {
                "reconciliation": ReconciliationSerializer(reconciliation).data,
                "lines": StatementLineSerializer(
                    reconciliation.statement.lines.all(), many=True
                ).data,
            }
        )


class BankTransferViewSet(BankingViewPermissionMixin, NoDeleteViewSet):
    view_permission = "banking.view_banktransfer"
    queryset = BankTransfer.objects.select_related("from_account", "to_account").all()
    serializer_class = BankTransferSerializer
    search_fields = ("number", "reference", "from_account__code", "to_account__code")

    def create(self, request, *args, **kwargs):
        _require(request, "banking.manage_banktransfer")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, "banking.manage_banktransfer")
        return super().update(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(
            number=next_number("TRF"),
            requested_by=self.request.user,
            created_by=self.request.user,
            updated_by=self.request.user,
        )

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        _require(request, "banking.manage_banktransfer")
        transfer = self.get_object()
        if transfer.status != BankTransfer.Status.DRAFT:
            return error_response(
                "invalid_state", "Only a draft transfer can be submitted.", status.HTTP_409_CONFLICT
            )
        transfer.status = BankTransfer.Status.SUBMITTED
        transfer.submitted_at = timezone.now()
        transfer.updated_by = request.user
        transfer.save(update_fields=["status", "submitted_at", "updated_by", "updated_at"])
        _audit(
            request,
            "bank_transfer.submitted",
            "banking.banktransfer",
            transfer.pk,
            {"status": transfer.status},
        )
        return Response(self.get_serializer(transfer).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        _require(request, "banking.approve_banktransfer")
        transfer = self.get_object()
        if transfer.status != BankTransfer.Status.SUBMITTED:
            return error_response(
                "invalid_state",
                "Only a submitted transfer can be approved.",
                status.HTTP_409_CONFLICT,
            )
        if transfer.requested_by_id == request.user.pk:
            return error_response(
                "segregation_of_duties",
                "A transfer cannot be approved by its requester.",
                status.HTTP_409_CONFLICT,
            )
        transfer.status = BankTransfer.Status.APPROVED
        transfer.approved_by = request.user
        transfer.approved_at = timezone.now()
        transfer.updated_by = request.user
        transfer.save(
            update_fields=["status", "approved_by", "approved_at", "updated_by", "updated_at"]
        )
        _audit(
            request,
            "bank_transfer.approved",
            "banking.banktransfer",
            transfer.pk,
            {"status": transfer.status},
        )
        return Response(self.get_serializer(transfer).data)

    @action(detail=True, methods=["post"])
    def record(self, request, pk=None):
        _require(request, "banking.approve_banktransfer")
        try:
            transfer = record_transfer(self.get_object(), request.user)
        except BankingConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(transfer).data)


class CashAccountViewSet(BankingViewPermissionMixin, MasterDataViewSet):
    view_permission = "banking.view_cashaccount"
    queryset = CashAccount.objects.select_related("custodian").all()
    serializer_class = CashAccountSerializer
    search_fields = ("code", "name")

    def create(self, request, *args, **kwargs):
        _require(request, "banking.manage_pettycash")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, "banking.manage_pettycash")
        return super().update(request, *args, **kwargs)


class CashVoucherViewSet(BankingViewPermissionMixin, NoDeleteViewSet):
    view_permission = "banking.view_cashvoucher"
    queryset = CashVoucher.objects.select_related(
        "cash_account", "requested_by", "approved_by"
    ).all()
    serializer_class = CashVoucherSerializer
    search_fields = ("number", "payee", "description", "cash_account__code")

    def create(self, request, *args, **kwargs):
        _require(request, "banking.manage_pettycash")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, "banking.manage_pettycash")
        return super().update(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(
            number=next_number("CV"),
            requested_by=self.request.user,
            created_by=self.request.user,
            updated_by=self.request.user,
        )

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        _require(request, "banking.manage_pettycash")
        voucher = self.get_object()
        if voucher.status != CashVoucher.Status.DRAFT:
            return error_response(
                "invalid_state", "Only a draft voucher can be submitted.", status.HTTP_409_CONFLICT
            )
        voucher.status = CashVoucher.Status.SUBMITTED
        voucher.submitted_at = timezone.now()
        voucher.updated_by = request.user
        voucher.save(update_fields=["status", "submitted_at", "updated_by", "updated_at"])
        _audit(
            request,
            "cash_voucher.submitted",
            "banking.cashvoucher",
            voucher.pk,
            {"status": voucher.status},
        )
        return Response(self.get_serializer(voucher).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        _require(request, "banking.approve_cashvoucher")
        voucher = self.get_object()
        if voucher.status != CashVoucher.Status.SUBMITTED:
            return error_response(
                "invalid_state",
                "Only a submitted voucher can be approved.",
                status.HTTP_409_CONFLICT,
            )
        if voucher.requested_by_id == request.user.pk:
            return error_response(
                "segregation_of_duties",
                "A voucher cannot be approved by its requester.",
                status.HTTP_409_CONFLICT,
            )
        voucher.status = CashVoucher.Status.APPROVED
        voucher.approved_by = request.user
        voucher.approved_at = timezone.now()
        voucher.updated_by = request.user
        voucher.save(
            update_fields=["status", "approved_by", "approved_at", "updated_by", "updated_at"]
        )
        _audit(
            request,
            "cash_voucher.approved",
            "banking.cashvoucher",
            voucher.pk,
            {"status": voucher.status},
        )
        return Response(self.get_serializer(voucher).data)

    @action(detail=True, methods=["post"])
    def record(self, request, pk=None):
        _require(request, "banking.approve_cashvoucher")
        try:
            voucher = record_cash_voucher(self.get_object(), request.user)
        except BankingConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(voucher).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        _require(request, "banking.approve_cashvoucher")
        voucher = self.get_object()
        reason = (request.data.get("reason") or "").strip()
        if voucher.status != CashVoucher.Status.SUBMITTED or not reason:
            return error_response(
                "invalid_state",
                "A submitted voucher and a reason are required.",
                status.HTTP_409_CONFLICT,
            )
        voucher.status = CashVoucher.Status.REJECTED
        voucher.rejection_reason = reason
        voucher.updated_by = request.user
        voucher.save(update_fields=["status", "rejection_reason", "updated_by", "updated_at"])
        _audit(
            request, "cash_voucher.rejected", "banking.cashvoucher", voucher.pk, {"reason": reason}
        )
        return Response(self.get_serializer(voucher).data)


class PettyCashReplenishmentViewSet(BankingViewPermissionMixin, NoDeleteViewSet):
    view_permission = "banking.view_pettycashreplenishment"
    queryset = PettyCashReplenishment.objects.select_related("cash_account", "bank_account").all()
    serializer_class = PettyCashReplenishmentSerializer
    search_fields = ("number", "reference", "cash_account__code", "bank_account__code")

    def create(self, request, *args, **kwargs):
        _require(request, "banking.manage_pettycash")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, "banking.manage_pettycash")
        return super().update(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(
            number=next_number("PCR"),
            requested_by=self.request.user,
            created_by=self.request.user,
            updated_by=self.request.user,
        )

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        _require(request, "banking.approve_cashvoucher")
        replenishment = self.get_object()
        if replenishment.status != PettyCashReplenishment.Status.SUBMITTED:
            return error_response(
                "invalid_state",
                "Only a submitted replenishment can be approved.",
                status.HTTP_409_CONFLICT,
            )
        if replenishment.requested_by_id == request.user.pk:
            return error_response(
                "segregation_of_duties",
                "A replenishment cannot be approved by its requester.",
                status.HTTP_409_CONFLICT,
            )
        replenishment.status = PettyCashReplenishment.Status.APPROVED
        replenishment.approved_by = request.user
        replenishment.approved_at = timezone.now()
        replenishment.updated_by = request.user
        replenishment.save(
            update_fields=["status", "approved_by", "approved_at", "updated_by", "updated_at"]
        )
        _audit(
            request,
            "petty_cash_replenishment.approved",
            "banking.pettycashreplenishment",
            replenishment.pk,
            {"status": replenishment.status},
        )
        return Response(self.get_serializer(replenishment).data)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        _require(request, "banking.manage_pettycash")
        replenishment = self.get_object()
        if replenishment.status != PettyCashReplenishment.Status.DRAFT:
            return error_response(
                "invalid_state",
                "Only a draft replenishment can be submitted.",
                status.HTTP_409_CONFLICT,
            )
        replenishment.status = PettyCashReplenishment.Status.SUBMITTED
        replenishment.submitted_at = timezone.now()
        replenishment.updated_by = request.user
        replenishment.save(update_fields=["status", "submitted_at", "updated_by", "updated_at"])
        _audit(
            request,
            "petty_cash_replenishment.submitted",
            "banking.pettycashreplenishment",
            replenishment.pk,
            {"status": replenishment.status},
        )
        return Response(self.get_serializer(replenishment).data)

    @action(detail=True, methods=["post"])
    def record(self, request, pk=None):
        _require(request, "banking.approve_cashvoucher")
        try:
            replenishment = record_replenishment(self.get_object(), request.user)
        except BankingConflict as exc:
            return _conflict(exc)
        return Response(self.get_serializer(replenishment).data)


def _paged(request, rows: list[dict]) -> Response:
    try:
        page = max(int(request.query_params.get("page", "1")), 1)
        size = min(max(int(request.query_params.get("page_size", "25")), 1), 100)
    except ValueError:
        page, size = 1, 25
    start = (page - 1) * size
    return Response({"count": len(rows), "results": rows[start : start + size]})


class BankingSummaryView(APIView):
    def get(self, request):
        _require(request, "banking.view_bankaccount")
        rows = [account_summary(account) for account in BankAccount.objects.all()]
        return _paged(request, rows)


class ReconciliationReportView(APIView):
    def get(self, request):
        _require(request, "banking.view_reconciliation")
        account = request.query_params.get("bank_account")
        return _paged(
            request,
            report_rows(BankAccount.objects.filter(pk=account).first() if account else None),
        )


class UnmatchedTransactionsView(APIView):
    def get(self, request):
        _require(request, "banking.view_statementline")
        lines = StatementLine.objects.filter(
            status__in=[StatementLine.Status.UNMATCHED, StatementLine.Status.PARTIALLY_MATCHED]
        ).select_related("statement", "statement__bank_account")
        rows = [
            {
                "id": line.pk,
                "statement": line.statement.number,
                "bank_account": line.statement.bank_account.code,
                "line_number": line.line_number,
                "value_date": line.value_date.isoformat(),
                "description": line.description,
                "reference": line.reference,
                "amount": str(line.amount),
                "status": line.status,
                "duplicate_status": line.duplicate_status,
                "classification": line.classification,
            }
            for line in lines
        ]
        return _paged(request, rows)


class MatchSuggestionsView(APIView):
    def get(self, request):
        _require(request, "banking.match_banktransaction")
        lines = StatementLine.objects.filter(status=StatementLine.Status.UNMATCHED).select_related(
            "statement", "statement__bank_account"
        )
        rows = []
        for line in lines:
            for suggestion in suggestions_for_line(line)[:5]:
                rows.append(
                    {
                        "line_id": line.pk,
                        "statement": line.statement.number,
                        "bank_account": line.statement.bank_account.code,
                        "value_date": line.value_date.isoformat(),
                        "description": line.description,
                        **suggestion,
                    }
                )
        return _paged(request, rows)


class CashPositionView(APIView):
    def get(self, request):
        _require(request, "banking.view_cashaccount")
        rows = []
        for account in CashAccount.objects.all():
            rows.append(
                {
                    "id": account.pk,
                    "code": account.code,
                    "name": account.name,
                    "currency": account.currency,
                    "opening_balance": str(account.opening_balance or ""),
                    "imprest_amount": str(account.imprest_amount or ""),
                    "recorded_vouchers": account.vouchers.filter(
                        status=CashVoucher.Status.RECORDED
                    ).count(),
                }
            )
        return _paged(request, rows)
