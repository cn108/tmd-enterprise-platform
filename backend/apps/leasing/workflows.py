"""Rental, reservation and equipment movement rules."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.core.approvals import creator_cannot_decide
from apps.core.models import create_audit_event
from apps.leasing.models import (
    Equipment,
    EquipmentInspection,
    EquipmentMaintenance,
    EquipmentMovement,
    EquipmentReservation,
    RentalAgreement,
)
from apps.procurement.numbering import next_number

ZERO = Decimal("0")


class LeasingConflict(Exception):
    pass


def _audit(actor, action: str, entity, after: dict) -> None:
    create_audit_event(
        actor=actor,
        action=action,
        entity_type=f"leasing.{entity._meta.model_name}",
        entity_id=entity.pk,
        after=after,
    )


def _bookings(
    equipment: Equipment, start: date, end: date, exclude_agreement=None, exclude_reservation=None
):
    agreements = RentalAgreement.objects.filter(
        lines__equipment=equipment,
        status__in=[
            RentalAgreement.Status.SUBMITTED,
            RentalAgreement.Status.APPROVED,
            RentalAgreement.Status.ACTIVE,
        ],
        start_date__lte=end,
        end_date__gte=start,
    )
    if exclude_agreement:
        agreements = agreements.exclude(pk=exclude_agreement.pk)
    reservations = EquipmentReservation.objects.filter(
        equipment=equipment,
        status__in=[
            EquipmentReservation.Status.TENTATIVE,
            EquipmentReservation.Status.CONFIRMED,
        ],
        start_date__lte=end,
        end_date__gte=start,
    )
    if exclude_reservation:
        reservations = reservations.exclude(pk=exclude_reservation.pk)
    return agreements, reservations


def check_availability(
    equipment: Equipment,
    start: date,
    end: date,
    *,
    exclude_agreement=None,
    exclude_reservation=None,
) -> None:
    if end < start:
        raise LeasingConflict("The booking cannot end before it starts.")
    if equipment.status == Equipment.Status.RETIRED:
        raise LeasingConflict(f"{equipment.code} is retired.")
    if equipment.status == Equipment.Status.MAINTENANCE:
        raise LeasingConflict(f"{equipment.code} is under maintenance.")
    agreements, reservations = _bookings(
        equipment, start, end, exclude_agreement, exclude_reservation
    )
    if agreements.exists() or reservations.exists():
        raise LeasingConflict(f"{equipment.code} already has an overlapping booking.")


@transaction.atomic
def approve_agreement(agreement: RentalAgreement, actor) -> RentalAgreement:
    agreement = RentalAgreement.objects.select_for_update().get(pk=agreement.pk)
    if agreement.status not in {RentalAgreement.Status.DRAFT, RentalAgreement.Status.SUBMITTED}:
        raise LeasingConflict("Only a draft or submitted agreement can be approved.")
    if creator_cannot_decide(actor, agreement.requested_by_id):
        raise LeasingConflict("A rental agreement cannot be approved by its requester.")
    if not agreement.lines.exists():
        raise LeasingConflict("A rental agreement needs at least one equipment line.")
    for line in agreement.lines.select_related("equipment"):
        check_availability(
            line.equipment,
            max(line.start_date, agreement.start_date),
            min(line.end_date, agreement.end_date),
            exclude_agreement=agreement,
        )
    agreement.status = RentalAgreement.Status.APPROVED
    agreement.approved_by = actor
    agreement.approved_at = timezone.now()
    agreement.updated_by = actor
    agreement.save(
        update_fields=["status", "approved_by", "approved_at", "updated_by", "updated_at"]
    )
    for line in agreement.lines.select_related("equipment"):
        if line.equipment.status == Equipment.Status.AVAILABLE:
            line.equipment.status = Equipment.Status.RESERVED
            line.equipment.updated_by = actor
            line.equipment.save(update_fields=["status", "updated_by", "updated_at"])
    _audit(actor, "rental_agreement.approved", agreement, {"status": agreement.status})
    return agreement


@transaction.atomic
def dispatch_equipment(
    agreement: RentalAgreement,
    actor,
    *,
    equipment: Equipment,
    on_date: date,
    condition="good",
    expected_return=None,
    notes="",
) -> EquipmentMovement:
    agreement = RentalAgreement.objects.select_for_update().get(pk=agreement.pk)
    equipment = Equipment.objects.select_for_update().get(pk=equipment.pk)
    if agreement.status not in {RentalAgreement.Status.APPROVED, RentalAgreement.Status.ACTIVE}:
        raise LeasingConflict("Only an approved or active agreement can dispatch equipment.")
    if not agreement.lines.filter(equipment=equipment).exists():
        raise LeasingConflict("That equipment is not on this agreement.")
    latest = (
        EquipmentMovement.objects.filter(agreement=agreement, equipment=equipment)
        .order_by("-movement_date", "-id")
        .first()
    )
    if latest and latest.kind == EquipmentMovement.Kind.DISPATCH:
        raise LeasingConflict("This equipment is already dispatched on the agreement.")
    movement = EquipmentMovement.objects.create(
        number=next_number("EMV"),
        equipment=equipment,
        agreement=agreement,
        kind=EquipmentMovement.Kind.DISPATCH,
        movement_date=on_date,
        expected_return_date=expected_return or agreement.end_date,
        condition=condition,
        handled_by=actor,
        notes=notes,
        created_by=actor,
        updated_by=actor,
    )
    equipment.status = Equipment.Status.RENTED
    equipment.location = f"On rent — {agreement.customer.legal_name}"
    equipment.updated_by = actor
    equipment.save(update_fields=["status", "location", "updated_by", "updated_at"])
    agreement.status = RentalAgreement.Status.ACTIVE
    agreement.updated_by = actor
    agreement.save(update_fields=["status", "updated_by", "updated_at"])
    _audit(
        actor,
        "equipment.dispatched",
        equipment,
        {"agreement": agreement.pk, "movement": movement.pk},
    )
    return movement


@transaction.atomic
def return_equipment(
    agreement: RentalAgreement | None,
    actor,
    *,
    equipment: Equipment,
    on_date: date,
    condition="good",
    notes="",
) -> EquipmentMovement:
    equipment = Equipment.objects.select_for_update().get(pk=equipment.pk)
    latest = (
        EquipmentMovement.objects.filter(equipment=equipment)
        .order_by("-movement_date", "-id")
        .first()
    )
    if latest is None or latest.kind != EquipmentMovement.Kind.DISPATCH:
        raise LeasingConflict("This equipment is not currently dispatched.")
    movement = EquipmentMovement.objects.create(
        number=next_number("EMV"),
        equipment=equipment,
        agreement=agreement or latest.agreement,
        kind=EquipmentMovement.Kind.RETURN,
        movement_date=on_date,
        condition=condition,
        handled_by=actor,
        notes=notes,
        created_by=actor,
        updated_by=actor,
    )
    equipment.status = (
        Equipment.Status.MAINTENANCE
        if condition in {EquipmentMovement.Condition.DAMAGED, EquipmentMovement.Condition.UNUSABLE}
        else Equipment.Status.AVAILABLE
    )
    equipment.location = (
        "Returned — awaiting inspection"
        if equipment.status == Equipment.Status.MAINTENANCE
        else "Company yard"
    )
    equipment.updated_by = actor
    equipment.save(update_fields=["status", "location", "updated_by", "updated_at"])
    if (
        movement.agreement
        and not EquipmentMovement.objects.filter(
            agreement=movement.agreement, kind=EquipmentMovement.Kind.DISPATCH
        )
        .exclude(kind=EquipmentMovement.Kind.RETURN)
        .exists()
    ):
        pass
    _audit(
        actor, "equipment.returned", equipment, {"movement": movement.pk, "condition": condition}
    )
    return movement


@transaction.atomic
def complete_maintenance(record: EquipmentMaintenance, actor) -> EquipmentMaintenance:
    record = EquipmentMaintenance.objects.select_for_update().get(pk=record.pk)
    if record.status not in {
        EquipmentMaintenance.Status.PLANNED,
        EquipmentMaintenance.Status.IN_PROGRESS,
    }:
        raise LeasingConflict("Only planned or in-progress maintenance can be completed.")
    record.status = EquipmentMaintenance.Status.COMPLETED
    record.completed_date = record.completed_date or timezone.localdate()
    record.updated_by = actor
    record.save(update_fields=["status", "completed_date", "updated_by", "updated_at"])
    if record.equipment.status == Equipment.Status.MAINTENANCE:
        other_open = (
            record.equipment.maintenance_records.filter(
                status__in=[
                    EquipmentMaintenance.Status.PLANNED,
                    EquipmentMaintenance.Status.IN_PROGRESS,
                ]
            )
            .exclude(pk=record.pk)
            .exists()
        )
        if not other_open:
            record.equipment.status = Equipment.Status.AVAILABLE
            record.equipment.updated_by = actor
            record.equipment.save(update_fields=["status", "updated_by", "updated_at"])
    _audit(actor, "equipment_maintenance.completed", record, {"status": record.status})
    return record


def utilisation_rows(start: date, end: date) -> list[dict]:
    """Rented calendar days divided by the requested calendar days."""
    total_days = max((end - start).days + 1, 1)
    rows = []
    for equipment in Equipment.objects.all():
        rented_days = 0
        for line in equipment.rental_lines.filter(
            agreement__status__in=[
                RentalAgreement.Status.APPROVED,
                RentalAgreement.Status.ACTIVE,
                RentalAgreement.Status.CLOSED,
            ]
        ).select_related("agreement"):
            overlap_start = max(start, line.start_date)
            overlap_end = min(end, line.end_date)
            if overlap_end >= overlap_start:
                rented_days += (overlap_end - overlap_start).days + 1
        rows.append(
            {
                "id": equipment.pk,
                "code": equipment.code,
                "name": equipment.name,
                "status": equipment.status,
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "available_days": total_days,
                "rented_days": rented_days,
                "utilisation_percent": f"{(rented_days / total_days * 100):.2f}",
                "asset_classification": equipment.asset_classification,
            }
        )
    return rows


def warning_rows() -> list[dict]:
    today = timezone.localdate()
    rows = []
    for agreement in RentalAgreement.objects.filter(
        status__in=[RentalAgreement.Status.APPROVED, RentalAgreement.Status.ACTIVE],
        end_date__lt=today,
    ):
        rows.append(
            {
                "kind": "overdue_rental",
                "severity": "high",
                "reference": agreement.number,
                "equipment": "",
                "date": agreement.end_date.isoformat(),
                "message": f"Rental agreement {agreement.number} is past its end date.",
            }
        )
    for agreement in RentalAgreement.objects.filter(
        status__in=[RentalAgreement.Status.APPROVED, RentalAgreement.Status.ACTIVE],
        end_date__gte=today,
        end_date__lte=today + timedelta(days=30),
    ):
        rows.append(
            {
                "kind": "expiring_agreement",
                "severity": "medium",
                "reference": agreement.number,
                "equipment": "",
                "date": agreement.end_date.isoformat(),
                "message": f"Rental agreement {agreement.number} expires within 30 days.",
            }
        )
    latest_movements = {}
    for movement in EquipmentMovement.objects.select_related("equipment", "agreement").order_by(
        "equipment_id", "-movement_date", "-id"
    ):
        latest_movements.setdefault(movement.equipment_id, movement)
    for movement in latest_movements.values():
        if movement.kind != EquipmentMovement.Kind.DISPATCH:
            continue
        due = movement.expected_return_date or (
            movement.agreement.end_date if movement.agreement_id else None
        )
        if due and due <= today + timedelta(days=7):
            kind = "overdue_return" if due < today else "due_return"
            rows.append(
                {
                    "kind": kind,
                    "severity": "high" if due < today else "medium",
                    "reference": movement.agreement.number
                    if movement.agreement_id
                    else movement.number,
                    "equipment": movement.equipment.code,
                    "date": due.isoformat(),
                    "message": (
                        f"{movement.equipment.code} is overdue for return."
                        if due < today
                        else f"{movement.equipment.code} is due back within 7 days."
                    ),
                }
            )
    for maintenance in EquipmentMaintenance.objects.select_related("equipment").filter(
        status__in=[EquipmentMaintenance.Status.PLANNED, EquipmentMaintenance.Status.IN_PROGRESS]
    ):
        rows.append(
            {
                "kind": "maintenance",
                "severity": "medium",
                "reference": str(maintenance.pk),
                "equipment": maintenance.equipment.code,
                "date": maintenance.scheduled_date.isoformat(),
                "message": f"{maintenance.equipment.code} has open {maintenance.kind} maintenance.",
            }
        )
    return rows


def availability_rows(start: date, end: date) -> list[dict]:
    rows = []
    for equipment in Equipment.objects.filter(is_active=True).exclude(
        status=Equipment.Status.RETIRED
    ):
        agreements, reservations = _bookings(equipment, start, end)
        bookings = [
            {
                "type": "agreement",
                "reference": agreement.number,
                "start_date": agreement.start_date.isoformat(),
                "end_date": agreement.end_date.isoformat(),
                "status": agreement.status,
            }
            for agreement in agreements.distinct()
        ] + [
            {
                "type": "reservation",
                "reference": str(reservation.pk),
                "start_date": reservation.start_date.isoformat(),
                "end_date": reservation.end_date.isoformat(),
                "status": reservation.status,
            }
            for reservation in reservations
        ]
        rows.append(
            {
                "id": equipment.pk,
                "code": equipment.code,
                "name": equipment.name,
                "status": equipment.status,
                "location": equipment.location,
                "available": not bookings
                and equipment.status not in {Equipment.Status.MAINTENANCE},
                "bookings": bookings,
            }
        )
    return rows


def rental_inspection(record: EquipmentInspection, actor) -> EquipmentInspection:
    if record.damage_found and not record.damage_description.strip():
        raise LeasingConflict("Describe the damage found.")
    if record.damage_found:
        record.equipment.status = Equipment.Status.MAINTENANCE
        record.equipment.updated_by = actor
        record.equipment.save(update_fields=["status", "updated_by", "updated_at"])
    _audit(actor, "equipment_inspection.recorded", record, {"damage": record.damage_found})
    return record
