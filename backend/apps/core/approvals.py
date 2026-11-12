"""Independent approval arithmetic shared by every document type."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Q

from apps.core.models import ApprovalPolicy, ApprovalRecord, create_audit_event


class ApprovalError(Exception):
    """The approval cannot be recorded under the configured policy."""


@dataclass(frozen=True)
class ApprovalOutcome:
    policy: ApprovalPolicy | None
    required: int
    recorded: int
    final: bool
    record: ApprovalRecord


def resolve_policy(
    document_type: str,
    amount: Decimal | int | str | None = None,
    on_date: date | None = None,
) -> ApprovalPolicy | None:
    """Return the active band for a document, if one is configured.

    A missing policy falls back to one approval. The fallback is deliberately
    conservative but explicit: the caller still enforces a permission and the
    creator/requester separation, and the report shows that no band exists.
    """

    value = Decimal(str(amount or 0))
    target = on_date or date.today()
    return (
        ApprovalPolicy.objects.filter(
            document_type=document_type,
            is_active=True,
            effective_from__lte=target,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=target))
        .filter(min_amount__lte=value)
        .filter(Q(max_amount__isnull=True) | Q(max_amount__gt=value))
        .order_by("-min_amount", "-effective_from")
        .first()
    )


def approvals_required(
    document_type: str,
    amount: Decimal | int | str | None = None,
    on_date: date | None = None,
) -> int:
    policy = resolve_policy(document_type, amount, on_date)
    return policy.required_approvals if policy else 1


def approval_records(document_type: str, document_id: int):
    return ApprovalRecord.objects.filter(
        document_type=document_type,
        document_id=document_id,
        decision=ApprovalRecord.Decision.APPROVED,
    ).select_related("approver")


def approval_state(document_type: str, document_id: int, amount=None) -> dict:
    policy = resolve_policy(document_type, amount)
    required = policy.required_approvals if policy else 1
    recorded = approval_records(document_type, document_id).count()
    return {
        "required": required,
        "recorded": recorded,
        "final": recorded >= required,
        "policy": policy.code if policy else None,
    }


@transaction.atomic
def register_approval(
    *,
    document_type: str,
    document_id: int,
    approver,
    amount,
    creators: set[int] | None = None,
    decision: str = ApprovalRecord.Decision.APPROVED,
    notes: str = "",
    actor=None,
) -> ApprovalOutcome:
    """Record one person's decision and report whether the document is final.

    The same person cannot decide twice, and a creator/requester cannot decide
    at all. Both rules are enforced here rather than in a view so a new endpoint
    cannot bypass them.
    """

    creators = creators or set()
    if getattr(approver, "pk", None) in creators:
        raise ApprovalError("A document cannot be approved by its creator or requester.")
    policy = resolve_policy(document_type, amount)
    required = policy.required_approvals if policy else 1
    if (
        policy is not None
        and policy.required_role_id is not None
        and not approver.is_superuser
        and not approver.groups.filter(pk=policy.required_role_id).exists()
    ):
        raise ApprovalError("This approval band requires a different role.")

    existing = ApprovalRecord.objects.filter(document_type=document_type, document_id=document_id)
    if existing.filter(approver=approver).exists():
        raise ApprovalError("This person has already decided on the document.")
    if decision == ApprovalRecord.Decision.REJECTED:
        record = ApprovalRecord.objects.create(
            policy=policy,
            document_type=document_type,
            document_id=document_id,
            approver=approver,
            decision=decision,
            amount=amount,
            notes=notes,
        )
        create_audit_event(
            actor=actor or approver,
            action="approval.rejected",
            entity_type=document_type,
            entity_id=document_id,
            after={"approver": approver.pk, "amount": str(amount), "notes": notes},
        )
        return ApprovalOutcome(policy, required, 0, False, record)

    recorded = existing.filter(decision=ApprovalRecord.Decision.APPROVED).count() + 1
    record = ApprovalRecord.objects.create(
        policy=policy,
        document_type=document_type,
        document_id=document_id,
        approver=approver,
        decision=decision,
        amount=amount,
        notes=notes,
    )
    create_audit_event(
        actor=actor or approver,
        action="approval.recorded",
        entity_type=document_type,
        entity_id=document_id,
        after={
            "approver": approver.pk,
            "amount": str(amount),
            "required": required,
            "recorded": recorded,
        },
    )
    return ApprovalOutcome(policy, required, recorded, recorded >= required, record)
