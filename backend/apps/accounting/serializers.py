from __future__ import annotations

from rest_framework import serializers

from apps.accounting.models import (
    Account,
    AccountingPeriod,
    AccountingSettings,
    FiscalYear,
    JournalEntry,
    JournalLine,
    OpeningBalance,
    OpeningBalanceLine,
    PostingRule,
    PostingRuleLine,
)
from apps.catalogue.models import CatalogueItem
from apps.organisation.models import CostCentre
from apps.parties.models import Party
from apps.projects.models import Project

from .numbering import next_number


class AccountSerializer(serializers.ModelSerializer):
    is_approved = serializers.BooleanField(read_only=True)
    approved_by = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = [
            "id",
            "code",
            "name",
            "account_type",
            "normal_balance",
            "parent",
            "description",
            "is_active",
            "is_approved",
            "approved_by",
            "approved_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["approved_by", "approved_at", "created_at", "updated_at"]

    def get_approved_by(self, obj: Account) -> str | None:
        return obj.approved_by.email if obj.approved_by else None

    def validate_parent(self, value):
        if value is None:
            return value
        if self.instance and value.pk == self.instance.pk:
            raise serializers.ValidationError("An account cannot be its own parent.")
        ancestor = value
        seen: set[int] = set()
        while ancestor is not None:
            if ancestor.pk in seen or (self.instance and ancestor.pk == self.instance.pk):
                raise serializers.ValidationError("Accounts cannot form a cycle.")
            seen.add(ancestor.pk)
            ancestor = ancestor.parent
        return value


class FiscalYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = FiscalYear
        fields = ["id", "code", "name", "start_date", "end_date", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError(
                {"end_date": "The end date cannot precede the start date."}
            )
        return attrs


class AccountingPeriodSerializer(serializers.ModelSerializer):
    closed_by = serializers.SerializerMethodField()

    class Meta:
        model = AccountingPeriod
        fields = [
            "id",
            "fiscal_year",
            "name",
            "start_date",
            "end_date",
            "status",
            "closed_at",
            "closed_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["status", "closed_at", "closed_by", "created_at", "updated_at"]

    def get_closed_by(self, obj: AccountingPeriod) -> str | None:
        return obj.closed_by.email if obj.closed_by else None

    def validate(self, attrs):
        year = attrs.get("fiscal_year", getattr(self.instance, "fiscal_year", None))
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if year and start and end:
            if end < start:
                raise serializers.ValidationError(
                    {"end_date": "The end date cannot precede the start date."}
                )
            if start < year.start_date or end > year.end_date:
                raise serializers.ValidationError("A period must fall inside its fiscal year.")
            overlap = AccountingPeriod.objects.filter(
                fiscal_year=year, start_date__lte=end, end_date__gte=start
            )
            if self.instance:
                overlap = overlap.exclude(pk=self.instance.pk)
            if overlap.exists():
                raise serializers.ValidationError("Accounting periods cannot overlap.")
        return attrs


class JournalLineInputSerializer(serializers.Serializer):
    account = serializers.PrimaryKeyRelatedField(queryset=Account.objects.all())
    debit = serializers.DecimalField(
        max_digits=18, decimal_places=2, min_value=0, required=False, default=0
    )
    credit = serializers.DecimalField(
        max_digits=18, decimal_places=2, min_value=0, required=False, default=0
    )
    description = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(), required=False, allow_null=True
    )
    cost_centre = serializers.PrimaryKeyRelatedField(
        queryset=CostCentre.objects.all(), required=False, allow_null=True
    )
    party = serializers.PrimaryKeyRelatedField(
        queryset=Party.objects.all(), required=False, allow_null=True
    )
    item = serializers.PrimaryKeyRelatedField(
        queryset=CatalogueItem.objects.all(), required=False, allow_null=True
    )


class JournalCreateSerializer(serializers.Serializer):
    journal_date = serializers.DateField()
    period = serializers.PrimaryKeyRelatedField(queryset=AccountingPeriod.objects.all())
    description = serializers.CharField(max_length=255)
    source_type = serializers.ChoiceField(
        choices=[
            (JournalEntry.Source.MANUAL, "Manual"),
            (JournalEntry.Source.ADJUSTMENT, "Adjustment"),
        ],
        required=False,
        default=JournalEntry.Source.MANUAL,
    )
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    lines = JournalLineInputSerializer(many=True)

    def validate_lines(self, value):
        if len(value) < 2:
            raise serializers.ValidationError("A journal needs at least two lines.")
        return value

    def validate(self, attrs):
        if (
            attrs.get("source_type") == JournalEntry.Source.ADJUSTMENT
            and not attrs.get("reason", "").strip()
        ):
            raise serializers.ValidationError({"reason": "An adjustment journal needs a reason."})
        return attrs


class JournalLineSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source="account.code", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)

    class Meta:
        model = JournalLine
        fields = [
            "id",
            "line_number",
            "account",
            "account_code",
            "account_name",
            "debit",
            "credit",
            "description",
            "project",
            "cost_centre",
            "party",
            "item",
        ]


class JournalSerializer(serializers.ModelSerializer):
    lines = JournalLineSerializer(many=True, read_only=True)
    created_by = serializers.SerializerMethodField()
    submitted_by = serializers.SerializerMethodField()
    approved_by = serializers.SerializerMethodField()
    posted_by = serializers.SerializerMethodField()

    class Meta:
        model = JournalEntry
        fields = [
            "id",
            "number",
            "journal_date",
            "period",
            "description",
            "source_type",
            "reason",
            "status",
            "total_debit",
            "total_credit",
            "submitted_at",
            "submitted_by",
            "approved_at",
            "approved_by",
            "posted_at",
            "posted_by",
            "reversal_of",
            "posting_rule",
            "event_reference",
            "lines",
            "created_by",
            "created_at",
        ]

    def _email(self, obj, field: str) -> str | None:
        user = getattr(obj, field)
        return user.email if user else None

    def get_created_by(self, obj: JournalEntry) -> str | None:
        return self._email(obj, "created_by")

    def get_submitted_by(self, obj: JournalEntry) -> str | None:
        return self._email(obj, "submitted_by")

    def get_approved_by(self, obj: JournalEntry) -> str | None:
        return self._email(obj, "approved_by")

    def get_posted_by(self, obj: JournalEntry) -> str | None:
        return self._email(obj, "posted_by")


class JournalReverseSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)
    period = serializers.PrimaryKeyRelatedField(
        queryset=AccountingPeriod.objects.all(), required=False, allow_null=True
    )
    journal_date = serializers.DateField(required=False, allow_null=True)

    def validate_reason(self, value):
        if not value.strip():
            raise serializers.ValidationError("A reversal needs a reason.")
        return value


class OpeningBalanceLineInputSerializer(serializers.Serializer):
    account = serializers.PrimaryKeyRelatedField(queryset=Account.objects.all())
    debit = serializers.DecimalField(
        max_digits=18, decimal_places=2, min_value=0, required=False, default=0
    )
    credit = serializers.DecimalField(
        max_digits=18, decimal_places=2, min_value=0, required=False, default=0
    )
    description = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(), required=False, allow_null=True
    )
    cost_centre = serializers.PrimaryKeyRelatedField(
        queryset=CostCentre.objects.all(), required=False, allow_null=True
    )


class OpeningBalanceCreateSerializer(serializers.Serializer):
    fiscal_year = serializers.PrimaryKeyRelatedField(queryset=FiscalYear.objects.all())
    period = serializers.PrimaryKeyRelatedField(queryset=AccountingPeriod.objects.all())
    as_of_date = serializers.DateField()
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    lines = OpeningBalanceLineInputSerializer(many=True)

    def validate(self, attrs):
        if attrs["period"].fiscal_year_id != attrs["fiscal_year"].pk:
            raise serializers.ValidationError(
                {"period": "The period belongs to a different fiscal year."}
            )
        if not (
            attrs["fiscal_year"].start_date <= attrs["as_of_date"] <= attrs["fiscal_year"].end_date
        ):
            raise serializers.ValidationError(
                {"as_of_date": "The date falls outside the fiscal year."}
            )
        if not attrs["lines"]:
            raise serializers.ValidationError({"lines": "Add at least one line."})
        if OpeningBalance.objects.filter(fiscal_year=attrs["fiscal_year"]).exists():
            raise serializers.ValidationError(
                {"fiscal_year": "This fiscal year already has an opening balance."}
            )
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        lines = validated_data.pop("lines")
        opening = OpeningBalance.objects.create(
            number=next_number("OB"),
            created_by=request.user,
            updated_by=request.user,
            **validated_data,
        )
        for index, line in enumerate(lines, start=1):
            OpeningBalanceLine.objects.create(opening_balance=opening, line_number=index, **line)
        return opening


class OpeningBalanceLineSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source="account.code", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)

    class Meta:
        model = OpeningBalanceLine
        fields = [
            "id",
            "line_number",
            "account",
            "account_code",
            "account_name",
            "debit",
            "credit",
            "description",
            "project",
            "cost_centre",
        ]


class OpeningBalanceSerializer(serializers.ModelSerializer):
    lines = OpeningBalanceLineSerializer(many=True, read_only=True)
    posted_by = serializers.SerializerMethodField()
    posted_journal_number = serializers.CharField(
        source="posted_journal.number", read_only=True, default=None
    )

    class Meta:
        model = OpeningBalance
        fields = [
            "id",
            "number",
            "fiscal_year",
            "period",
            "as_of_date",
            "notes",
            "status",
            "posted_journal",
            "posted_journal_number",
            "posted_at",
            "posted_by",
            "lines",
            "created_at",
        ]

    def get_posted_by(self, obj: OpeningBalance) -> str | None:
        return obj.posted_by.email if obj.posted_by else None


class PostingRuleLineInputSerializer(serializers.Serializer):
    account = serializers.PrimaryKeyRelatedField(queryset=Account.objects.all())
    direction = serializers.ChoiceField(choices=PostingRuleLine.Direction.choices)
    amount_key = serializers.CharField(max_length=60)

    def validate_amount_key(self, value):
        if not value.strip():
            raise serializers.ValidationError("An amount key is required.")
        return value.strip()


class PostingRuleCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=60)
    name = serializers.CharField(max_length=120)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    lines = PostingRuleLineInputSerializer(many=True)

    def validate_code(self, value):
        code = value.strip().lower()
        if PostingRule.objects.filter(code=code).exists():
            raise serializers.ValidationError("A posting rule with this code exists.")
        return code

    def validate_lines(self, value):
        if not value:
            raise serializers.ValidationError("A posting rule needs at least one line.")
        return value

    def create(self, validated_data):
        request = self.context["request"]
        lines = validated_data.pop("lines")
        rule = PostingRule.objects.create(
            created_by=request.user, updated_by=request.user, **validated_data
        )
        for index, line in enumerate(lines, start=1):
            PostingRuleLine.objects.create(rule=rule, line_number=index, **line)
        return rule


class PostingRuleLineSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source="account.code", read_only=True)

    class Meta:
        model = PostingRuleLine
        fields = ["id", "line_number", "account", "account_code", "direction", "amount_key"]


class PostingRuleSerializer(serializers.ModelSerializer):
    lines = PostingRuleLineSerializer(many=True, read_only=True)
    approved_by = serializers.SerializerMethodField()

    class Meta:
        model = PostingRule
        fields = [
            "id",
            "code",
            "name",
            "description",
            "is_active",
            "approved_by",
            "approved_at",
            "lines",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["approved_by", "approved_at", "created_at", "updated_at"]

    def get_approved_by(self, obj: PostingRule) -> str | None:
        return obj.approved_by.email if obj.approved_by else None


class PostingEventSerializer(serializers.Serializer):
    journal_date = serializers.DateField()
    period = serializers.PrimaryKeyRelatedField(queryset=AccountingPeriod.objects.all())
    description = serializers.CharField(max_length=255)
    reference = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    amounts = serializers.DictField(
        child=serializers.DecimalField(max_digits=18, decimal_places=2, min_value=0)
    )
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(), required=False, allow_null=True
    )
    cost_centre = serializers.PrimaryKeyRelatedField(
        queryset=CostCentre.objects.all(), required=False, allow_null=True
    )
    party = serializers.PrimaryKeyRelatedField(
        queryset=Party.objects.all(), required=False, allow_null=True
    )

    def validate_amounts(self, value):
        if not value:
            raise serializers.ValidationError("Provide the event amounts.")
        return value


class AccountingSettingsSerializer(serializers.ModelSerializer):
    retained_earnings_account_code = serializers.CharField(
        source="retained_earnings_account.code", read_only=True, default=None
    )

    class Meta:
        model = AccountingSettings
        fields = [
            "retained_earnings_account",
            "retained_earnings_account_code",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]
