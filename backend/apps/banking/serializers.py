from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

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


class BankAccountSerializer(serializers.ModelSerializer):
    gl_account_code = serializers.CharField(source="gl_account.code", read_only=True)
    masked_account = serializers.CharField(read_only=True)

    class Meta:
        model = BankAccount
        fields = [
            "id",
            "code",
            "name",
            "bank_name",
            "branch",
            "account_name",
            "account_last4",
            "masked_account",
            "sort_code",
            "swift_code",
            "currency",
            "classification",
            "opening_balance",
            "opening_balance_date",
            "gl_account",
            "gl_account_code",
            "is_active",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["masked_account", "created_at", "updated_at"]

    def validate(self, attrs):
        opening = attrs.get("opening_balance", getattr(self.instance, "opening_balance", None))
        opening_date = attrs.get(
            "opening_balance_date", getattr(self.instance, "opening_balance_date", None)
        )
        if opening is not None and opening_date is None:
            raise serializers.ValidationError(
                {"opening_balance_date": "Record the date the opening balance applies to."}
            )
        if opening_date is not None and opening is None:
            raise serializers.ValidationError(
                {"opening_balance": "Record the opening balance with its date."}
            )
        gl_account = attrs.get("gl_account", getattr(self.instance, "gl_account", None))
        if gl_account is not None and not gl_account.is_approved:
            raise serializers.ValidationError(
                {"gl_account": "Only an approved chart-of-accounts entry can be linked."}
            )
        return attrs


class BankingSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankingSettings
        fields = [
            "id",
            "amount_tolerance",
            "date_tolerance_days",
            "auto_suggest_enabled",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]

    def validate_amount_tolerance(self, value):
        if value < 0:
            raise serializers.ValidationError("A tolerance cannot be negative.")
        return value


class StatementLineSerializer(serializers.ModelSerializer):
    statement_number = serializers.CharField(source="statement.number", read_only=True)
    account_code = serializers.CharField(source="statement.bank_account.code", read_only=True)
    matched_amount = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    remaining_amount = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)

    class Meta:
        model = StatementLine
        fields = [
            "id",
            "statement",
            "statement_number",
            "account_code",
            "line_number",
            "value_date",
            "description",
            "reference",
            "debit",
            "credit",
            "amount",
            "balance",
            "external_id",
            "status",
            "duplicate_status",
            "duplicate_of",
            "classification",
            "exclusion_reason",
            "matched_amount",
            "remaining_amount",
            "created_at",
        ]
        read_only_fields = fields


class BankStatementSerializer(serializers.ModelSerializer):
    bank_account_code = serializers.CharField(source="bank_account.code", read_only=True)
    line_count = serializers.SerializerMethodField()
    reconciliation_number = serializers.SerializerMethodField()
    source_file = serializers.FileField(write_only=True)
    column_mapping = serializers.JSONField(write_only=True, required=False)
    rows = serializers.ListField(child=serializers.DictField(), read_only=True)

    class Meta:
        model = BankStatement
        fields = [
            "id",
            "number",
            "bank_account",
            "bank_account_code",
            "reference",
            "period_start",
            "period_end",
            "currency",
            "opening_balance",
            "closing_balance",
            "status",
            "source_file",
            "original_filename",
            "file_sha256",
            "row_count",
            "line_count",
            "reconciliation_number",
            "column_mapping",
            "rows",
            "imported_by",
            "imported_at",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "number",
            "currency",
            "status",
            "original_filename",
            "file_sha256",
            "row_count",
            "imported_by",
            "imported_at",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def get_line_count(self, obj: BankStatement) -> int:
        return obj.lines.count()

    def get_reconciliation_number(self, obj: BankStatement) -> str:
        reconciliation = getattr(obj, "reconciliation", None)
        return reconciliation.number if reconciliation else ""

    def validate_source_file(self, upload):
        if not upload.name.lower().endswith((".csv", ".xlsx")):
            raise serializers.ValidationError("Upload a CSV or XLSX bank statement.")
        if upload.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("The statement file is larger than 10 MB.")
        return upload

    def validate(self, attrs):
        if attrs["period_end"] < attrs["period_start"]:
            raise serializers.ValidationError(
                {"period_end": "The period cannot end before it starts."}
            )
        if attrs.get("opening_balance") is not None and attrs.get("closing_balance") is None:
            raise serializers.ValidationError(
                {"closing_balance": "Record the statement closing balance."}
            )
        return attrs


class BankTransactionSerializer(serializers.ModelSerializer):
    bank_account_code = serializers.CharField(source="bank_account.code", read_only=True)
    matched_amount = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    remaining_amount = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)

    class Meta:
        model = BankTransaction
        fields = [
            "id",
            "number",
            "bank_account",
            "bank_account_code",
            "transaction_date",
            "description",
            "reference",
            "currency",
            "amount",
            "source_type",
            "source_id",
            "external_reference",
            "status",
            "matched_amount",
            "remaining_amount",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "number",
            "source_type",
            "source_id",
            "status",
            "matched_amount",
            "remaining_amount",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        account = attrs.get("bank_account") or getattr(self.instance, "bank_account", None)
        currency = attrs.get("currency") or getattr(self.instance, "currency", None)
        if account and currency and account.currency != currency:
            raise serializers.ValidationError(
                {"currency": "The transaction currency must match the bank account."}
            )
        if self.instance and self.instance.matches.filter(status="confirmed").exists():
            raise serializers.ValidationError(
                "A matched transaction cannot be edited. Remove its matches first."
            )
        return attrs


class ReconciliationMatchSerializer(serializers.ModelSerializer):
    statement_line_number = serializers.IntegerField(
        source="statement_line.line_number", read_only=True
    )
    transaction_number = serializers.CharField(
        source="bank_transaction.number", read_only=True, default=""
    )
    matched_by_email = serializers.CharField(source="matched_by.email", read_only=True, default="")

    class Meta:
        model = ReconciliationMatch
        fields = [
            "id",
            "reconciliation",
            "statement_line",
            "statement_line_number",
            "bank_transaction",
            "transaction_number",
            "amount",
            "match_type",
            "status",
            "confidence",
            "matched_by",
            "matched_by_email",
            "matched_at",
            "notes",
            "created_at",
        ]
        read_only_fields = fields


class ReconciliationSerializer(serializers.ModelSerializer):
    bank_account_code = serializers.CharField(source="bank_account.code", read_only=True)
    statement_number = serializers.CharField(source="statement.number", read_only=True)
    unmatched_count = serializers.IntegerField(read_only=True)
    excluded_count = serializers.IntegerField(read_only=True)
    difference = serializers.DecimalField(
        max_digits=18, decimal_places=2, read_only=True, allow_null=True
    )
    matches = ReconciliationMatchSerializer(many=True, read_only=True)
    prepared_by_email = serializers.CharField(
        source="prepared_by.email", read_only=True, default=""
    )
    approved_by_email = serializers.CharField(
        source="approved_by.email", read_only=True, default=""
    )

    class Meta:
        model = Reconciliation
        fields = [
            "id",
            "number",
            "bank_account",
            "bank_account_code",
            "statement",
            "statement_number",
            "period_start",
            "period_end",
            "statement_opening_balance",
            "statement_closing_balance",
            "status",
            "prepared_by",
            "prepared_by_email",
            "submitted_at",
            "approved_by",
            "approved_by_email",
            "approved_at",
            "rejection_reason",
            "posting_status",
            "posting_blocker",
            "unmatched_count",
            "excluded_count",
            "difference",
            "matches",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class BankTransferSerializer(serializers.ModelSerializer):
    from_account_code = serializers.CharField(source="from_account.code", read_only=True)
    to_account_code = serializers.CharField(source="to_account.code", read_only=True)

    class Meta:
        model = BankTransfer
        fields = [
            "id",
            "number",
            "from_account",
            "from_account_code",
            "to_account",
            "to_account_code",
            "transfer_date",
            "amount",
            "reference",
            "status",
            "requested_by",
            "submitted_at",
            "approved_by",
            "approved_at",
            "recorded_by",
            "recorded_at",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "number",
            "status",
            "requested_by",
            "submitted_at",
            "approved_by",
            "approved_at",
            "recorded_by",
            "recorded_at",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        source = attrs.get("from_account") or getattr(self.instance, "from_account", None)
        target = attrs.get("to_account") or getattr(self.instance, "to_account", None)
        if source and target and source.pk == target.pk:
            raise serializers.ValidationError(
                {"to_account": "Choose a different destination account."}
            )
        if source and target and source.currency != target.currency:
            raise serializers.ValidationError(
                {"to_account": "The source and destination currencies must match."}
            )
        if self.instance and self.instance.status != "draft":
            raise serializers.ValidationError("Only a draft transfer can be edited.")
        return attrs


class CashAccountSerializer(serializers.ModelSerializer):
    custodian_email = serializers.CharField(source="custodian.email", read_only=True, default="")
    balance = serializers.SerializerMethodField()

    class Meta:
        model = CashAccount
        fields = [
            "id",
            "code",
            "name",
            "currency",
            "custodian",
            "custodian_email",
            "imprest_amount",
            "opening_balance",
            "balance",
            "is_active",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["balance", "created_at", "updated_at"]

    def get_balance(self, obj: CashAccount) -> str:
        if obj.opening_balance is None:
            return ""
        from django.db.models import Sum

        receipts = obj.vouchers.filter(
            status=CashVoucher.Status.RECORDED,
            kind__in=[CashVoucher.Kind.RECEIPT, CashVoucher.Kind.REPLENISHMENT],
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        payments = obj.vouchers.filter(
            status=CashVoucher.Status.RECORDED,
            kind__in=[CashVoucher.Kind.EXPENSE, CashVoucher.Kind.PAYMENT],
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        return str(obj.opening_balance + receipts - payments)


class CashVoucherSerializer(serializers.ModelSerializer):
    cash_account_code = serializers.CharField(source="cash_account.code", read_only=True)
    requested_by_email = serializers.CharField(
        source="requested_by.email", read_only=True, default=""
    )
    approved_by_email = serializers.CharField(
        source="approved_by.email", read_only=True, default=""
    )

    class Meta:
        model = CashVoucher
        fields = [
            "id",
            "number",
            "cash_account",
            "cash_account_code",
            "kind",
            "voucher_date",
            "payee",
            "description",
            "amount",
            "status",
            "receipt_reference",
            "requested_by",
            "requested_by_email",
            "submitted_at",
            "approved_by",
            "approved_by_email",
            "approved_at",
            "recorded_by",
            "recorded_at",
            "rejection_reason",
            "cancel_reason",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "number",
            "status",
            "requested_by",
            "submitted_at",
            "approved_by",
            "approved_at",
            "recorded_by",
            "recorded_at",
            "rejection_reason",
            "cancel_reason",
            "created_at",
            "updated_at",
        ]

    def validate_cash_account(self, value):
        if not value.is_active:
            raise serializers.ValidationError("Choose an active cash account.")
        return value


class PettyCashReplenishmentSerializer(serializers.ModelSerializer):
    cash_account_code = serializers.CharField(source="cash_account.code", read_only=True)
    bank_account_code = serializers.CharField(source="bank_account.code", read_only=True)

    class Meta:
        model = PettyCashReplenishment
        fields = [
            "id",
            "number",
            "cash_account",
            "cash_account_code",
            "bank_account",
            "bank_account_code",
            "replenishment_date",
            "amount",
            "reference",
            "status",
            "requested_by",
            "submitted_at",
            "approved_by",
            "approved_at",
            "recorded_by",
            "recorded_at",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "number",
            "status",
            "requested_by",
            "submitted_at",
            "approved_by",
            "approved_at",
            "recorded_by",
            "recorded_at",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        cash = attrs.get("cash_account") or getattr(self.instance, "cash_account", None)
        bank = attrs.get("bank_account") or getattr(self.instance, "bank_account", None)
        if cash and bank and cash.currency != bank.currency:
            raise serializers.ValidationError(
                {"bank_account": "The bank and cash account currencies must match."}
            )
        return attrs
