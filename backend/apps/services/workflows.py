"""Service workflow services and guarded transitions."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.core.models import create_audit_event
from apps.procurement.numbering import next_number
from apps.services.models import (
    ServiceChecklistItem,
    ServiceContract,
    WorkOrder,
    WorkOrderAssignment,
    WorkOrderProgress,
    WorkOrderReport,
)


class ServiceConflict(Exception):
    pass


def _audit(actor, action: str, entity, after: dict) -> None:
    create_audit_event(
        actor=actor,
        action=action,
        entity_type=f"services.{entity._meta.model_name}",
        entity_id=entity.pk,
        after=after,
    )


@transaction.atomic
def schedule_work_order(work_order: WorkOrder, actor, *, start, end) -> WorkOrder:
    work_order = WorkOrder.objects.select_for_update().get(pk=work_order.pk)
    if work_order.status not in {WorkOrder.Status.DRAFT, WorkOrder.Status.ON_HOLD}:
        raise ServiceConflict("Only a draft or on-hold work order can be scheduled.")
    if start and end and end < start:
        raise ServiceConflict("The scheduled end cannot precede the start.")
    work_order.scheduled_start = start
    work_order.scheduled_end = end
    work_order.status = WorkOrder.Status.SCHEDULED
    work_order.updated_by = actor
    work_order.save(
        update_fields=["scheduled_start", "scheduled_end", "status", "updated_by", "updated_at"]
    )
    _audit(actor, "work_order.scheduled", work_order, {"start": str(start), "end": str(end)})
    return work_order


@transaction.atomic
def start_work_order(work_order: WorkOrder, actor, *, started_on=None) -> WorkOrder:
    work_order = WorkOrder.objects.select_for_update().get(pk=work_order.pk)
    if work_order.status != WorkOrder.Status.SCHEDULED:
        raise ServiceConflict("Only a scheduled work order can be started.")
    work_order.status = WorkOrder.Status.IN_PROGRESS
    work_order.actual_start = started_on or timezone.localdate()
    work_order.progress_percent = max(work_order.progress_percent, 1)
    work_order.updated_by = actor
    work_order.save(
        update_fields=[
            "status",
            "actual_start",
            "progress_percent",
            "updated_by",
            "updated_at",
        ]
    )
    _audit(actor, "work_order.started", work_order, {"started_on": str(work_order.actual_start)})
    return work_order


@transaction.atomic
def update_progress(
    work_order: WorkOrder,
    actor,
    *,
    percent: int,
    notes: str = "",
    labour_hours=None,
    materials_used: str = "",
) -> WorkOrder:
    work_order = WorkOrder.objects.select_for_update().get(pk=work_order.pk)
    if work_order.status not in {WorkOrder.Status.IN_PROGRESS, WorkOrder.Status.ON_HOLD}:
        raise ServiceConflict("Progress can only be recorded while work is open.")
    if percent < 0 or percent > 100:
        raise ServiceConflict("Progress must be between 0 and 100.")
    if percent < work_order.progress_percent:
        raise ServiceConflict("Progress cannot move backwards.")
    record = WorkOrderProgress.objects.create(
        work_order=work_order,
        progress_date=timezone.localdate(),
        percent_complete=percent,
        notes=notes,
        labour_hours=labour_hours,
        materials_used=materials_used,
        reported_by=actor,
        created_by=actor,
        updated_by=actor,
    )
    work_order.progress_percent = percent
    work_order.updated_by = actor
    work_order.save(update_fields=["progress_percent", "updated_by", "updated_at"])
    _audit(
        actor,
        "work_order.progress_recorded",
        work_order,
        {"progress": record.pk, "percent": percent},
    )
    return work_order


@transaction.atomic
def assign_person(work_order: WorkOrder, actor, *, user, role="", planned_hours=None):
    work_order = WorkOrder.objects.select_for_update().get(pk=work_order.pk)
    if work_order.status in {
        WorkOrder.Status.COMPLETED,
        WorkOrder.Status.ACCEPTED,
        WorkOrder.Status.CANCELLED,
    }:
        raise ServiceConflict("Closed work cannot receive new assignments.")
    if WorkOrderAssignment.objects.filter(work_order=work_order, user=user).exists():
        raise ServiceConflict("This person is already assigned to the work order.")
    assignment = WorkOrderAssignment.objects.create(
        work_order=work_order,
        user=user,
        role=role,
        planned_hours=planned_hours,
        assigned_at=timezone.now(),
        created_by=actor,
        updated_by=actor,
    )
    _audit(actor, "work_order.assigned", work_order, {"user": user.pk, "assignment": assignment.pk})
    return assignment


@transaction.atomic
def complete_work_order(work_order: WorkOrder, actor) -> WorkOrder:
    work_order = WorkOrder.objects.select_for_update().get(pk=work_order.pk)
    if work_order.status != WorkOrder.Status.IN_PROGRESS:
        raise ServiceConflict("Only work in progress can be completed.")
    required_open = work_order.checklist.filter(is_required=True, is_completed=False).count()
    if required_open:
        raise ServiceConflict(f"{required_open} required checklist item(s) are still open.")
    report = getattr(work_order, "completion_report", None)
    if report is None or report.status not in {
        WorkOrderReport.Status.SUBMITTED,
        WorkOrderReport.Status.ACCEPTED,
    }:
        raise ServiceConflict("Submit the completion report before completing the work order.")
    work_order.status = WorkOrder.Status.COMPLETED
    work_order.actual_end = work_order.actual_end or timezone.localdate()
    work_order.progress_percent = 100
    work_order.updated_by = actor
    work_order.save(
        update_fields=["status", "actual_end", "progress_percent", "updated_by", "updated_at"]
    )
    _audit(actor, "work_order.completed", work_order, {"report": report.pk})
    return work_order


@transaction.atomic
def accept_work_order(work_order: WorkOrder, actor, *, representative: str) -> WorkOrder:
    work_order = WorkOrder.objects.select_for_update().get(pk=work_order.pk)
    if work_order.status != WorkOrder.Status.COMPLETED:
        raise ServiceConflict("Only completed work can be accepted.")
    report = getattr(work_order, "completion_report", None)
    if report is None or report.status != WorkOrderReport.Status.SUBMITTED:
        raise ServiceConflict("A submitted completion report is required for acceptance.")
    if not representative.strip():
        raise ServiceConflict("Record the customer representative who accepted the work.")
    work_order.status = WorkOrder.Status.ACCEPTED
    work_order.updated_by = actor
    work_order.save(update_fields=["status", "updated_by", "updated_at"])
    report.status = WorkOrderReport.Status.ACCEPTED
    report.accepted_by = actor
    report.accepted_at = timezone.now()
    report.customer_representative = representative.strip()
    report.updated_by = actor
    report.save(
        update_fields=[
            "status",
            "accepted_by",
            "accepted_at",
            "customer_representative",
            "updated_by",
            "updated_at",
        ]
    )
    _audit(actor, "work_order.accepted", work_order, {"representative": representative.strip()})
    return work_order


@transaction.atomic
def submit_report(report: WorkOrderReport, actor) -> WorkOrderReport:
    report = WorkOrderReport.objects.select_for_update().get(pk=report.pk)
    if report.status not in {WorkOrderReport.Status.DRAFT, WorkOrderReport.Status.REJECTED}:
        raise ServiceConflict("Only a draft or rejected report can be submitted.")
    if not report.summary.strip():
        raise ServiceConflict("A report summary is required.")
    report.status = WorkOrderReport.Status.SUBMITTED
    report.submitted_by = actor
    report.submitted_at = timezone.now()
    report.updated_by = actor
    report.save(
        update_fields=["status", "submitted_by", "submitted_at", "updated_by", "updated_at"]
    )
    _audit(actor, "work_order_report.submitted", report, {"work_order": report.work_order_id})
    return report


@transaction.atomic
def activate_contract(contract: ServiceContract, actor) -> ServiceContract:
    contract = ServiceContract.objects.select_for_update().get(pk=contract.pk)
    if contract.status != ServiceContract.Status.DRAFT:
        raise ServiceConflict("Only a draft service contract can be activated.")
    if contract.created_by_id == actor.pk:
        raise ServiceConflict("A service contract cannot be activated by its creator.")
    contract.status = ServiceContract.Status.ACTIVE
    contract.approved_by = actor
    contract.approved_at = timezone.now()
    contract.updated_by = actor
    contract.save(
        update_fields=["status", "approved_by", "approved_at", "updated_by", "updated_at"]
    )
    _audit(actor, "service_contract.activated", contract, {"status": contract.status})
    return contract


def create_work_order_number() -> str:
    return next_number("WO")


def create_contract_number() -> str:
    return next_number("SC")


def ensure_checklist(work_order: WorkOrder, actor) -> list[ServiceChecklistItem]:
    """Create a checklist row from the order's HSE requirements when empty."""
    if work_order.checklist.exists():
        return list(work_order.checklist.all())
    if not work_order.hse_requirements.strip():
        return []
    return [
        ServiceChecklistItem.objects.create(
            work_order=work_order,
            sequence=1,
            description=work_order.hse_requirements.strip()[:255],
            is_required=True,
            created_by=actor,
            updated_by=actor,
        )
    ]
