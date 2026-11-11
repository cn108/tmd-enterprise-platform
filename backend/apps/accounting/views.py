from __future__ import annotations

from datetime import date
from decimal import Decimal

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounting.models import (
    Account,
    AccountingPeriod,
    AccountingSettings,
    FiscalYear,
    JournalEntry,
    OpeningBalance,
    PostingRule,
)
from apps.accounting.serializers import (
    AccountingPeriodSerializer,
    AccountingSettingsSerializer,
    AccountSerializer,
    FiscalYearSerializer,
    JournalCreateSerializer,
    JournalReverseSerializer,
    JournalSerializer,
    OpeningBalanceCreateSerializer,
    OpeningBalanceSerializer,
    PostingEventSerializer,
    PostingRuleCreateSerializer,
    PostingRuleSerializer,
)
from apps.accounting.services import (
    Conflict,
    approve_account,
    approve_journal,
    approve_posting_rule,
    close_period,
    configure_retained_earnings,
    create_journal,
    financial_statements,
    general_ledger,
    post_event,
    post_journal,
    post_opening_balance,
    reverse_journal,
    submit_journal,
    trial_balance,
)
from shared.exceptions import error_response
from shared.viewsets import NoDeleteViewSet

MANAGE_ACCOUNTS = "accounting.manage_accounts"
APPROVE_ACCOUNT = "accounting.approve_account"
MANAGE_FISCAL_YEARS = "accounting.manage_fiscalyears"
MANAGE_PERIODS = "accounting.manage_periods"
CLOSE_PERIOD = "accounting.close_period"
CREATE_JOURNAL = "accounting.create_journal"
APPROVE_JOURNAL = "accounting.approve_journal"
POST_JOURNAL = "accounting.post_journal"
REVERSE_JOURNAL = "accounting.reverse_journal"
MANAGE_OPENING = "accounting.manage_openingbalance"
MANAGE_RULES = "accounting.manage_postingrules"
APPROVE_RULE = "accounting.approve_postingrule"
CONFIGURE = "accounting.configure_accounting"


def _require(request, permission: str) -> None:
    if not request.user.has_perm(permission):
        raise PermissionDenied("You do not have permission for this action.")


def _conflict(exc: Conflict) -> Response:
    return error_response("invalid_state", str(exc), status.HTTP_409_CONFLICT)


def _bad_request(message: str, code: str = "invalid_filter") -> Response:
    return error_response(code, message, status.HTTP_400_BAD_REQUEST)


def _not_found(message: str) -> Response:
    return error_response("not_found", message, status.HTTP_404_NOT_FOUND)


def _strings(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _strings(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_strings(item) for item in value]
    if isinstance(value, date):
        return value.isoformat()
    return value


def _date_param(raw: str, name: str) -> date:
    try:
        return date.fromisoformat(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an ISO date (YYYY-MM-DD).") from exc


class AccountViewSet(NoDeleteViewSet):
    queryset = Account.objects.select_related("parent", "approved_by").all()
    serializer_class = AccountSerializer
    search_fields = ("code", "name")

    def create(self, request, *args, **kwargs):
        _require(request, MANAGE_ACCOUNTS)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, MANAGE_ACCOUNTS)
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        _require(request, APPROVE_ACCOUNT)
        try:
            account = approve_account(self.get_object(), request.user)
        except Conflict as exc:
            return _conflict(exc)
        return Response(AccountSerializer(account).data)


class FiscalYearViewSet(NoDeleteViewSet):
    queryset = FiscalYear.objects.all()
    serializer_class = FiscalYearSerializer
    search_fields = ("code", "name")

    def create(self, request, *args, **kwargs):
        _require(request, MANAGE_FISCAL_YEARS)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, MANAGE_FISCAL_YEARS)
        return super().update(request, *args, **kwargs)


class AccountingPeriodViewSet(NoDeleteViewSet):
    queryset = AccountingPeriod.objects.select_related("fiscal_year", "closed_by").all()
    serializer_class = AccountingPeriodSerializer
    search_fields = ("name", "fiscal_year__code")

    def create(self, request, *args, **kwargs):
        _require(request, MANAGE_PERIODS)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _require(request, MANAGE_PERIODS)
        instance = self.get_object()
        if instance.status == AccountingPeriod.Status.CLOSED:
            return error_response(
                "invalid_state",
                "A closed period cannot be edited; open a correction period instead.",
                status.HTTP_409_CONFLICT,
            )
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="close")
    def close_period(self, request, pk=None):
        _require(request, CLOSE_PERIOD)
        try:
            period = close_period(self.get_object(), request.user)
        except Conflict as exc:
            return _conflict(exc)
        return Response(AccountingPeriodSerializer(period).data)


class JournalViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = JournalEntry.objects.select_related(
        "period",
        "created_by",
        "submitted_by",
        "approved_by",
        "posted_by",
        "reversal_of",
        "posting_rule",
    ).prefetch_related("lines")

    def get_serializer_class(self):
        return JournalCreateSerializer if self.action == "create" else JournalSerializer

    def create(self, request, *args, **kwargs):
        _require(request, CREATE_JOURNAL)
        payload = self.get_serializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            journal = create_journal(actor=request.user, **payload.validated_data)
        except Conflict as exc:
            return _conflict(exc)
        return Response(JournalSerializer(journal).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="submit")
    def submit_journal(self, request, pk=None):
        _require(request, CREATE_JOURNAL)
        try:
            journal = submit_journal(self.get_object(), request.user)
        except Conflict as exc:
            return _conflict(exc)
        return Response(JournalSerializer(journal).data)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve_journal(self, request, pk=None):
        _require(request, APPROVE_JOURNAL)
        try:
            journal = approve_journal(self.get_object(), request.user)
        except Conflict as exc:
            return _conflict(exc)
        return Response(JournalSerializer(journal).data)

    @action(detail=True, methods=["post"], url_path="post")
    def post_journal(self, request, pk=None):
        _require(request, POST_JOURNAL)
        try:
            journal = post_journal(self.get_object(), request.user)
        except Conflict as exc:
            return _conflict(exc)
        return Response(JournalSerializer(journal).data)

    @action(detail=True, methods=["post"], url_path="reverse")
    def reverse_journal(self, request, pk=None):
        _require(request, REVERSE_JOURNAL)
        payload = JournalReverseSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            reversal = reverse_journal(
                self.get_object(),
                request.user,
                payload.validated_data["reason"],
                period=payload.validated_data.get("period"),
                journal_date=payload.validated_data.get("journal_date"),
            )
        except Conflict as exc:
            return _conflict(exc)
        return Response(JournalSerializer(reversal).data, status=status.HTTP_201_CREATED)


class OpeningBalanceViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = OpeningBalance.objects.select_related(
        "fiscal_year", "period", "posted_by", "posted_journal"
    ).prefetch_related("lines")

    def get_serializer_class(self):
        return (
            OpeningBalanceCreateSerializer if self.action == "create" else OpeningBalanceSerializer
        )

    def create(self, request, *args, **kwargs):
        _require(request, MANAGE_OPENING)
        payload = self.get_serializer(data=request.data)
        payload.is_valid(raise_exception=True)
        opening = payload.save()
        return Response(OpeningBalanceSerializer(opening).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="post")
    def post_opening_balance(self, request, pk=None):
        _require(request, POST_JOURNAL)
        try:
            opening = post_opening_balance(self.get_object(), request.user)
        except Conflict as exc:
            return _conflict(exc)
        return Response(OpeningBalanceSerializer(opening).data)


class PostingRuleViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = PostingRule.objects.select_related("approved_by").prefetch_related("lines")

    def get_serializer_class(self):
        if self.action == "create":
            return PostingRuleCreateSerializer
        if self.action == "post_event":
            return PostingEventSerializer
        return PostingRuleSerializer

    def create(self, request, *args, **kwargs):
        _require(request, MANAGE_RULES)
        payload = self.get_serializer(data=request.data)
        payload.is_valid(raise_exception=True)
        rule = payload.save()
        return Response(PostingRuleSerializer(rule).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve_rule(self, request, pk=None):
        _require(request, APPROVE_RULE)
        try:
            rule = approve_posting_rule(self.get_object(), request.user)
        except Conflict as exc:
            return _conflict(exc)
        return Response(PostingRuleSerializer(rule).data)

    @action(detail=True, methods=["post"], url_path="post-event")
    def post_event(self, request, pk=None):
        _require(request, POST_JOURNAL)
        payload = self.get_serializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            journal = post_event(self.get_object(), request.user, **payload.validated_data)
        except Conflict as exc:
            return _conflict(exc)
        return Response(JournalSerializer(journal).data, status=status.HTTP_201_CREATED)


class AccountingSettingsView(APIView):
    def get(self, request):
        return Response(AccountingSettingsSerializer(AccountingSettings.load()).data)

    def patch(self, request):
        _require(request, CONFIGURE)
        account = None
        account_id = request.data.get("retained_earnings_account")
        if account_id is not None:
            account = Account.objects.filter(pk=account_id).first()
            if account is None:
                return _not_found("Unknown retained-earnings account.")
        try:
            settings = configure_retained_earnings(account, request.user)
        except Conflict as exc:
            return _conflict(exc)
        return Response(AccountingSettingsSerializer(settings).data)


class TrialBalanceView(APIView):
    def get(self, request):
        period_id = request.query_params.get("period")
        as_of_raw = request.query_params.get("as_of")
        if not period_id and not as_of_raw:
            return _bad_request("Supply period or as_of.")
        period = None
        as_of = None
        try:
            if period_id:
                period = AccountingPeriod.objects.filter(pk=int(period_id)).first()
                if period is None:
                    return _not_found("Unknown accounting period.")
            if as_of_raw:
                as_of = _date_param(as_of_raw, "as_of")
        except ValueError as exc:
            return _bad_request(str(exc))
        report = trial_balance(period=period, as_of=as_of)
        return Response(_strings(report))


class FinancialStatementsView(APIView):
    def get(self, request):
        start_raw = request.query_params.get("start")
        end_raw = request.query_params.get("end")
        if not start_raw or not end_raw:
            return _bad_request("Supply start and end dates.")
        try:
            start = _date_param(start_raw, "start")
            end = _date_param(end_raw, "end")
        except ValueError as exc:
            return _bad_request(str(exc))
        try:
            report = financial_statements(start=start, end=end)
        except Conflict as exc:
            return _conflict(exc)
        return Response(_strings(report))


class GeneralLedgerView(APIView):
    def get(self, request):
        account_id = request.query_params.get("account")
        if not account_id:
            return _bad_request("Supply an account.")
        try:
            account = Account.objects.get(pk=int(account_id))
        except (TypeError, ValueError):
            return _bad_request("account must be an integer.")
        except Account.DoesNotExist:
            return _not_found("Unknown account.")
        start = None
        end = None
        try:
            if request.query_params.get("start"):
                start = _date_param(request.query_params["start"], "start")
            if request.query_params.get("end"):
                end = _date_param(request.query_params["end"], "end")
        except ValueError as exc:
            return _bad_request(str(exc))
        return Response(_strings(general_ledger(account, start=start, end=end)))
