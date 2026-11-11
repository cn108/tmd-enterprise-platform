"""Inventory rules: one signed ledger, derived balances, configured valuation.

Every quantity change goes through :func:`_post_movement`. Nothing here writes a
balance row, so a balance cannot disagree with its movements. Outbound movements
are costed by the configured method, and the method is locked once movements
exist so reported costs cannot be silently rewritten.

No valuation method, reorder level or unit cost is invented: the method must be
recorded by an authorised user, and every inbound document must carry its cost.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from apps.catalogue.models import CatalogueItem
from apps.inventory.models import (
    ZERO,
    InventoryPolicy,
    ReorderLevel,
    StockAdjustment,
    StockAdjustmentLine,
    StockCount,
    StockCountLine,
    StockDamage,
    StockDamageLine,
    StockIssue,
    StockIssueLine,
    StockLayer,
    StockLayerConsumption,
    StockMovement,
    StockReceipt,
    StockReceiptLine,
    StockReservation,
    StockReturn,
    StockReturnLine,
    StockTransfer,
    StockTransferLine,
)
from apps.procurement.numbering import next_number
from apps.warehousing.models import Warehouse

CENT = Decimal("0.01")
QTY = Decimal("0.0001")
COST = Decimal("0.000001")

INBOUND = {
    StockMovement.Type.RECEIPT,
    StockMovement.Type.TRANSFER_IN,
    StockMovement.Type.RETURN_IN,
    StockMovement.Type.ADJUSTMENT_IN,
    StockMovement.Type.COUNT_GAIN,
}
OUTBOUND = {
    StockMovement.Type.TRANSFER_OUT,
    StockMovement.Type.ISSUE,
    StockMovement.Type.PROJECT_ISSUE,
    StockMovement.Type.ADJUSTMENT_OUT,
    StockMovement.Type.DAMAGE,
    StockMovement.Type.COUNT_LOSS,
}


class Conflict(Exception):
    """The record is valid but cannot be changed in its current state."""


class PolicyNotConfigured(Conflict):
    """No valuation method has been approved, so stock cannot be costed."""


def _quantize(value: Decimal, places: Decimal) -> Decimal:
    return value.quantize(places)


def policy() -> InventoryPolicy:
    return InventoryPolicy.load()


def valuation_method() -> str:
    method = policy().valuation_method
    if not method:
        raise PolicyNotConfigured(
            "No inventory valuation method is configured. An authorised user must "
            "record FIFO or weighted average before stock can be issued or valued."
        )
    return method


def set_policy(method: str, actor, note: str = "") -> InventoryPolicy:
    if method not in InventoryPolicy.Method.values:
        raise Conflict("Choose FIFO or weighted average.")
    record = policy()
    if (
        record.valuation_method
        and record.valuation_method != method
        and StockMovement.objects.exists()
    ):
        raise Conflict(
            "The valuation method cannot change once stock movements exist; "
            "changing it would restate costs already reported."
        )
    record.valuation_method = method
    record.note = note
    record.approved_by = actor
    record.approved_at = timezone.now()
    record.save()
    return record


def _lock_items(entries: Iterable[dict]) -> None:
    """Serialise movements per item so concurrent issues cannot oversell."""
    item_ids = sorted({entry["item"].pk for entry in entries})
    if item_ids:
        list(CatalogueItem.objects.select_for_update().filter(pk__in=item_ids).order_by("pk"))


def _assert_stock_item(item: CatalogueItem) -> None:
    if not item.is_stock_tracked:
        raise Conflict(f"{item.code} is a service and cannot be held in stock.")


def _assert_location(location, warehouse) -> None:
    if location is not None and location.warehouse_id != warehouse.pk:
        raise Conflict("The storage location belongs to a different warehouse.")


def _on_hand(item, warehouse) -> Decimal:
    total = StockMovement.objects.filter(item=item, warehouse=warehouse).aggregate(
        total=Sum("quantity")
    )["total"]
    return total or ZERO


def _ledger_value(item, warehouse) -> Decimal:
    total = StockMovement.objects.filter(item=item, warehouse=warehouse).aggregate(
        total=Sum("value_delta")
    )["total"]
    return total or ZERO


def _reserved(item, warehouse) -> Decimal:
    total = StockReservation.objects.filter(
        item=item, warehouse=warehouse, status=StockReservation.Status.OPEN
    ).aggregate(total=Sum(F("quantity") - F("quantity_fulfilled")))["total"]
    return total or ZERO


def available_quantity(item, warehouse) -> Decimal:
    return _quantize(_on_hand(item, warehouse) - _reserved(item, warehouse), QTY)


def _assert_available(item, warehouse, quantity: Decimal) -> None:
    available = available_quantity(item, warehouse)
    if quantity > available:
        raise Conflict(
            f"Only {available} of {item.code} is available at {warehouse.code} "
            f"(reservations are excluded); {quantity} was requested."
        )


def _consume_fifo(item, warehouse, quantity: Decimal):
    layers = list(
        StockLayer.objects.select_for_update()
        .filter(item=item, warehouse=warehouse, remaining_quantity__gt=0)
        .order_by("id")
    )
    need = quantity
    total = ZERO
    consumptions = []
    for layer in layers:
        if need <= 0:
            break
        take = min(layer.remaining_quantity, need)
        value = _quantize(take * layer.unit_cost, CENT)
        layer.remaining_quantity -= take
        layer.save(update_fields=["remaining_quantity"])
        consumptions.append((layer, take, layer.unit_cost, value))
        total += value
        need -= take
    if need > 0:
        raise Conflict(
            f"Only {quantity - need} of {item.code} is available at {warehouse.code}; "
            f"{quantity} was requested."
        )
    unit_cost = _quantize(total / quantity, COST) if quantity else ZERO
    return unit_cost, _quantize(total, CENT), consumptions


def _consume_weighted_average(item, warehouse, quantity: Decimal):
    on_hand = _on_hand(item, warehouse)
    if quantity > on_hand:
        raise Conflict(
            f"Only {on_hand} of {item.code} is on hand at {warehouse.code}; "
            f"{quantity} was requested."
        )
    value = _ledger_value(item, warehouse)
    if on_hand == 0:
        raise Conflict("There is no stock to cost.")
    unit_cost = _quantize(value / on_hand, COST)
    total = _quantize(quantity * unit_cost, CENT)
    if quantity == on_hand:
        total = _quantize(value, CENT)
    return unit_cost, total, []


def _consume(item, warehouse, quantity: Decimal):
    if valuation_method() == InventoryPolicy.Method.FIFO:
        return _consume_fifo(item, warehouse, quantity)
    return _consume_weighted_average(item, warehouse, quantity)


def _post_movement(
    movement_type: str,
    item,
    warehouse,
    quantity: Decimal,
    *,
    unit_cost: Decimal | None = None,
    value: Decimal | None = None,
    location=None,
    batch=None,
    serial=None,
    project=None,
    cost_centre=None,
    reference: str = "",
    reason: str = "",
    movement_date=None,
    actor=None,
    check_available: bool = True,
    goods_receipt_line=None,
    stock_receipt=None,
    transfer_line=None,
    issue_line=None,
    return_line=None,
    adjustment_line=None,
    damage_line=None,
    count_line=None,
) -> StockMovement:
    quantity = _quantize(Decimal(quantity), QTY)
    if quantity <= 0:
        raise Conflict("A stock movement needs a quantity greater than zero.")
    _assert_stock_item(item)
    _assert_location(location, warehouse)

    if movement_type in INBOUND:
        if unit_cost is None:
            raise Conflict("An inbound movement needs its unit cost.")
        unit_cost = _quantize(Decimal(unit_cost), COST)
        movement_value = _quantize(
            Decimal(value) if value is not None else quantity * unit_cost, CENT
        )
        signed_quantity = quantity
    elif movement_type in OUTBOUND:
        if check_available:
            _assert_available(item, warehouse, quantity)
        unit_cost, movement_value, consumptions = _consume(item, warehouse, quantity)
        signed_quantity = -quantity
    else:  # pragma: no cover - guarded by the choices
        raise Conflict("Unknown movement type.")

    movement = StockMovement.objects.create(
        number=next_number("SM"),
        movement_type=movement_type,
        item=item,
        warehouse=warehouse,
        location=location,
        batch=batch,
        serial=serial,
        quantity=signed_quantity,
        unit_cost=unit_cost,
        value_delta=movement_value if movement_type in INBOUND else -movement_value,
        project=project,
        cost_centre=cost_centre,
        reference=reference,
        reason=reason,
        movement_date=movement_date or timezone.localdate(),
        created_by=actor,
        goods_receipt_line=goods_receipt_line,
        stock_receipt=stock_receipt,
        transfer_line=transfer_line,
        issue_line=issue_line,
        return_line=return_line,
        adjustment_line=adjustment_line,
        damage_line=damage_line,
        count_line=count_line,
    )

    if movement_type in INBOUND:
        StockLayer.objects.create(
            item=item,
            warehouse=warehouse,
            movement=movement,
            unit_cost=unit_cost,
            original_quantity=quantity,
            remaining_quantity=quantity,
            received_on=movement.movement_date,
        )
    elif movement_type in OUTBOUND and valuation_method() == InventoryPolicy.Method.FIFO:
        for layer, taken, layer_cost, layer_value in consumptions:
            StockLayerConsumption.objects.create(
                layer=layer,
                movement=movement,
                quantity=taken,
                unit_cost=layer_cost,
                value=layer_value,
            )
    return movement


@transaction.atomic
def reserve_stock(
    *,
    item,
    warehouse,
    quantity,
    project=None,
    reference: str = "",
    notes: str = "",
    actor,
) -> StockReservation:
    _lock_items([{"item": item}])
    _assert_stock_item(item)
    quantity = _quantize(Decimal(quantity), QTY)
    if quantity <= 0:
        raise Conflict("A reservation needs a quantity greater than zero.")
    _assert_available(item, warehouse, quantity)
    return StockReservation.objects.create(
        item=item,
        warehouse=warehouse,
        project=project,
        quantity=quantity,
        reference=reference,
        notes=notes,
        created_by=actor,
        updated_by=actor,
    )


@transaction.atomic
def release_reservation(reservation: StockReservation, actor) -> StockReservation:
    if reservation.status != StockReservation.Status.OPEN:
        raise Conflict("Only an open reservation can be released.")
    reservation.status = StockReservation.Status.RELEASED
    reservation.updated_by = actor
    reservation.save(update_fields=["status", "updated_by", "updated_at"])
    return reservation


@transaction.atomic
def post_stock_receipt(
    *,
    warehouse,
    supplier=None,
    received_at,
    reference: str = "",
    notes: str = "",
    lines,
    actor,
) -> StockReceipt:
    if not lines:
        raise Conflict("A stock receipt needs at least one line.")
    _lock_items(lines)
    receipt = StockReceipt.objects.create(
        number=next_number("RCP"),
        warehouse=warehouse,
        supplier=supplier,
        received_at=received_at,
        reference=reference,
        notes=notes,
        received_by=actor,
        created_by=actor,
        updated_by=actor,
    )
    for entry in lines:
        line = StockReceiptLine.objects.create(
            receipt=receipt,
            item=entry["item"],
            quantity=entry["quantity"],
            unit_cost=entry["unit_cost"],
            batch=entry.get("batch"),
            serial=entry.get("serial"),
            created_by=actor,
            updated_by=actor,
        )
        _post_movement(
            StockMovement.Type.RECEIPT,
            entry["item"],
            warehouse,
            entry["quantity"],
            unit_cost=entry["unit_cost"],
            batch=entry.get("batch"),
            serial=entry.get("serial"),
            reference=receipt.number,
            movement_date=received_at,
            actor=actor,
            stock_receipt=receipt,
        )
        line.save()
    return receipt


def post_goods_receipt(receipt) -> None:
    """Post accepted quantities of a warehouse GRN into the stock ledger.

    Direct project or other-location deliveries are procurement facts, not
    company warehouse stock, so they do not create inventory movements.
    """
    lines = list(
        receipt.lines.select_related(
            "schedule__destination__warehouse", "order_line__item"
        ).order_by("id")
    )
    entries = []
    for line in lines:
        destination = line.schedule.destination
        if destination.kind != "warehouse":
            continue
        if line.quantity_accepted <= ZERO:
            continue
        if not line.order_line.item.is_stock_tracked:
            continue
        entries.append({"item": line.order_line.item, "line": line, "destination": destination})

    if not entries:
        return
    _lock_items(entries)
    for entry in entries:
        line = entry["line"]
        if StockMovement.objects.filter(goods_receipt_line=line).exists():
            continue
        _post_movement(
            StockMovement.Type.RECEIPT,
            entry["item"],
            entry["destination"].warehouse,
            line.quantity_accepted,
            unit_cost=line.order_line.unit_price,
            reference=receipt.number,
            movement_date=receipt.received_at,
            actor=receipt.received_by,
            goods_receipt_line=line,
        )


@transaction.atomic
def create_transfer(
    *,
    from_warehouse,
    from_location=None,
    to_warehouse,
    to_location=None,
    notes: str = "",
    lines,
    actor,
) -> StockTransfer:
    if not lines:
        raise Conflict("A transfer needs at least one line.")
    if from_warehouse.pk == to_warehouse.pk and ((from_location or None) == (to_location or None)):
        raise Conflict("A transfer must change warehouse or storage location.")
    _assert_location(from_location, from_warehouse)
    _assert_location(to_location, to_warehouse)
    transfer = StockTransfer.objects.create(
        number=next_number("TRF"),
        from_warehouse=from_warehouse,
        from_location=from_location,
        to_warehouse=to_warehouse,
        to_location=to_location,
        notes=notes,
        created_by=actor,
        updated_by=actor,
    )
    for entry in lines:
        StockTransferLine.objects.create(
            transfer=transfer,
            item=entry["item"],
            quantity=entry["quantity"],
            batch=entry.get("batch"),
            serial=entry.get("serial"),
            created_by=actor,
            updated_by=actor,
        )
    return transfer


@transaction.atomic
def dispatch_transfer(transfer: StockTransfer, actor) -> StockTransfer:
    if transfer.status != StockTransfer.Status.DRAFT:
        raise Conflict("Only a draft transfer can be dispatched.")
    lines = list(transfer.lines.select_related("item").order_by("id"))
    if not lines:
        raise Conflict("A transfer needs at least one line.")
    _lock_items([{"item": line.item} for line in lines])
    for line in lines:
        movement = _post_movement(
            StockMovement.Type.TRANSFER_OUT,
            line.item,
            transfer.from_warehouse,
            line.quantity,
            location=transfer.from_location,
            batch=line.batch,
            serial=line.serial,
            reference=transfer.number,
            actor=actor,
            transfer_line=line,
        )
        line.unit_cost = movement.unit_cost
        line.value = abs(movement.value_delta)
        line.updated_by = actor
        line.save(update_fields=["unit_cost", "value", "updated_by", "updated_at"])
    transfer.status = StockTransfer.Status.DISPATCHED
    transfer.dispatched_at = timezone.now()
    transfer.updated_by = actor
    transfer.save(update_fields=["status", "dispatched_at", "updated_by", "updated_at"])
    return transfer


@transaction.atomic
def receive_transfer(transfer: StockTransfer, actor) -> StockTransfer:
    if transfer.status != StockTransfer.Status.DISPATCHED:
        raise Conflict("Only a dispatched transfer can be received.")
    lines = list(transfer.lines.select_related("item").order_by("id"))
    _lock_items([{"item": line.item} for line in lines])
    for line in lines:
        if line.unit_cost is None or line.value is None:
            raise Conflict("The transfer line has no dispatched cost.")
        _post_movement(
            StockMovement.Type.TRANSFER_IN,
            line.item,
            transfer.to_warehouse,
            line.quantity,
            unit_cost=line.unit_cost,
            value=line.value,
            location=transfer.to_location,
            batch=line.batch,
            serial=line.serial,
            reference=transfer.number,
            actor=actor,
            transfer_line=line,
        )
    transfer.status = StockTransfer.Status.RECEIVED
    transfer.received_at = timezone.now()
    transfer.updated_by = actor
    transfer.save(update_fields=["status", "received_at", "updated_by", "updated_at"])
    return transfer


@transaction.atomic
def cancel_transfer(transfer: StockTransfer, actor) -> StockTransfer:
    if transfer.status != StockTransfer.Status.DRAFT:
        raise Conflict("Only a draft transfer can be cancelled; dispatched stock must be received.")
    transfer.status = StockTransfer.Status.CANCELLED
    transfer.updated_by = actor
    transfer.save(update_fields=["status", "updated_by", "updated_at"])
    return transfer


@transaction.atomic
def post_issue(
    *,
    project=None,
    cost_centre=None,
    recipient: str = "",
    notes: str = "",
    lines,
    actor,
) -> StockIssue:
    if not lines:
        raise Conflict("An issue needs at least one line.")
    _lock_items(lines)
    issue = StockIssue.objects.create(
        number=next_number("ISS"),
        project=project,
        cost_centre=cost_centre,
        recipient=recipient,
        notes=notes,
        issued_at=timezone.now(),
        issued_by=actor,
        created_by=actor,
        updated_by=actor,
    )
    for entry in lines:
        item = entry["item"]
        warehouse = entry["warehouse"]
        quantity = _quantize(Decimal(entry["quantity"]), QTY)
        reservation = entry.get("reservation")
        if reservation is not None:
            if reservation.status != StockReservation.Status.OPEN:
                raise Conflict("The reservation is not open.")
            if reservation.item_id != item.pk or reservation.warehouse_id != warehouse.pk:
                raise Conflict("The reservation is for a different item or warehouse.")
            if quantity > reservation.quantity_remaining:
                raise Conflict("The issue exceeds the remaining reserved quantity.")
            if quantity > _on_hand(item, warehouse):
                raise Conflict("There is not enough stock on hand to fulfil the reservation.")
        line = StockIssueLine.objects.create(
            issue=issue,
            item=item,
            warehouse=warehouse,
            location=entry.get("location"),
            quantity=quantity,
            batch=entry.get("batch"),
            serial=entry.get("serial"),
            reservation=reservation,
            created_by=actor,
            updated_by=actor,
        )
        movement = _post_movement(
            StockMovement.Type.PROJECT_ISSUE if project else StockMovement.Type.ISSUE,
            item,
            warehouse,
            quantity,
            location=entry.get("location"),
            batch=entry.get("batch"),
            serial=entry.get("serial"),
            project=project,
            cost_centre=cost_centre,
            reference=issue.number,
            actor=actor,
            check_available=reservation is None,
            issue_line=line,
        )
        line.unit_cost = movement.unit_cost
        line.value = abs(movement.value_delta)
        line.save(update_fields=["unit_cost", "value", "updated_at"])
        if reservation is not None:
            reservation.quantity_fulfilled += quantity
            if reservation.quantity_remaining <= 0:
                reservation.status = StockReservation.Status.FULFILLED
            reservation.updated_by = actor
            reservation.save(
                update_fields=["quantity_fulfilled", "status", "updated_by", "updated_at"]
            )
    return issue


@transaction.atomic
def post_return(*, project=None, notes: str = "", lines, actor) -> StockReturn:
    if not lines:
        raise Conflict("A return needs at least one line.")
    _lock_items(lines)
    document = StockReturn.objects.create(
        number=next_number("RET"),
        project=project,
        notes=notes,
        returned_at=timezone.now(),
        returned_by=actor,
        created_by=actor,
        updated_by=actor,
    )
    for entry in lines:
        line = StockReturnLine.objects.create(
            return_document=document,
            item=entry["item"],
            warehouse=entry["warehouse"],
            quantity=entry["quantity"],
            unit_cost=entry["unit_cost"],
            batch=entry.get("batch"),
            serial=entry.get("serial"),
            created_by=actor,
            updated_by=actor,
        )
        _post_movement(
            StockMovement.Type.RETURN_IN,
            entry["item"],
            entry["warehouse"],
            entry["quantity"],
            unit_cost=entry["unit_cost"],
            batch=entry.get("batch"),
            serial=entry.get("serial"),
            project=project,
            reference=document.number,
            actor=actor,
            return_line=line,
        )
    return document


@transaction.atomic
def post_adjustment(*, reason: str, lines, actor) -> StockAdjustment:
    if not reason.strip():
        raise Conflict("An adjustment needs a reason.")
    if not lines:
        raise Conflict("An adjustment needs at least one line.")
    _lock_items(lines)
    adjustment = StockAdjustment.objects.create(
        number=next_number("ADJ"),
        reason=reason.strip(),
        adjusted_at=timezone.now(),
        adjusted_by=actor,
        created_by=actor,
        updated_by=actor,
    )
    for entry in lines:
        item = entry["item"]
        warehouse = entry["warehouse"]
        quantity = entry["quantity"]
        direction = entry["direction"]
        unit_cost = entry.get("unit_cost")
        if direction == StockAdjustmentLine.Direction.INCREASE and unit_cost is None:
            raise Conflict("An increase needs the unit cost at which stock is added.")
        line = StockAdjustmentLine.objects.create(
            adjustment=adjustment,
            item=item,
            warehouse=warehouse,
            quantity=quantity,
            direction=direction,
            unit_cost=unit_cost,
            batch=entry.get("batch"),
            serial=entry.get("serial"),
            created_by=actor,
            updated_by=actor,
        )
        kind = (
            StockMovement.Type.ADJUSTMENT_IN
            if direction == StockAdjustmentLine.Direction.INCREASE
            else StockMovement.Type.ADJUSTMENT_OUT
        )
        movement = _post_movement(
            kind,
            item,
            warehouse,
            quantity,
            unit_cost=unit_cost,
            batch=entry.get("batch"),
            serial=entry.get("serial"),
            reason=adjustment.reason,
            reference=adjustment.number,
            actor=actor,
            adjustment_line=line,
        )
        line.unit_cost = movement.unit_cost
        line.value = abs(movement.value_delta)
        line.save(update_fields=["unit_cost", "value", "updated_at"])
    return adjustment


@transaction.atomic
def post_damage(*, reason: str, lines, actor) -> StockDamage:
    if not reason.strip():
        raise Conflict("Writing off damaged stock needs a reason.")
    if not lines:
        raise Conflict("A damage record needs at least one line.")
    _lock_items(lines)
    document = StockDamage.objects.create(
        number=next_number("DMG"),
        reason=reason.strip(),
        recorded_at=timezone.now(),
        recorded_by=actor,
        created_by=actor,
        updated_by=actor,
    )
    for entry in lines:
        line = StockDamageLine.objects.create(
            damage=document,
            item=entry["item"],
            warehouse=entry["warehouse"],
            location=entry.get("location"),
            quantity=entry["quantity"],
            batch=entry.get("batch"),
            serial=entry.get("serial"),
            created_by=actor,
            updated_by=actor,
        )
        movement = _post_movement(
            StockMovement.Type.DAMAGE,
            entry["item"],
            entry["warehouse"],
            entry["quantity"],
            location=entry.get("location"),
            batch=entry.get("batch"),
            serial=entry.get("serial"),
            reason=document.reason,
            reference=document.number,
            actor=actor,
            damage_line=line,
        )
        line.unit_cost = movement.unit_cost
        line.value = abs(movement.value_delta)
        line.save(update_fields=["unit_cost", "value", "updated_at"])
    return document


@transaction.atomic
def create_count(*, warehouse, notes: str = "", lines, actor) -> StockCount:
    if not lines:
        raise Conflict("A stock count needs at least one line.")
    count = StockCount.objects.create(
        number=next_number("CNT"),
        warehouse=warehouse,
        notes=notes,
        counted_by=actor,
        created_by=actor,
        updated_by=actor,
    )
    seen = set()
    for entry in lines:
        item = entry["item"]
        if item.pk in seen:
            raise Conflict("An item appears twice on the same count.")
        seen.add(item.pk)
        if not item.is_stock_tracked:
            raise Conflict(f"{item.code} is a service and cannot be counted.")
        StockCountLine.objects.create(
            count=count,
            item=item,
            batch=entry.get("batch"),
            counted_quantity=entry["counted_quantity"],
            unit_cost=entry.get("unit_cost"),
            created_by=actor,
            updated_by=actor,
        )
    return count


@transaction.atomic
def post_count(count: StockCount, actor) -> StockCount:
    if count.status != StockCount.Status.DRAFT:
        raise Conflict("Only a draft count can be posted.")
    lines = list(count.lines.select_related("item").order_by("id"))
    if not lines:
        raise Conflict("A count needs at least one line.")
    _lock_items([{"item": line.item} for line in lines])
    for line in lines:
        system_quantity = _on_hand(line.item, count.warehouse)
        variance = line.counted_quantity - system_quantity
        line.system_quantity = system_quantity
        line.variance = variance
        if variance > 0:
            unit_cost = line.unit_cost
            if unit_cost is None:
                if system_quantity <= 0:
                    raise Conflict(
                        f"{line.item.code} has no stock to derive a cost from; "
                        "supply a unit cost for the gain."
                    )
                unit_cost = _quantize(
                    _ledger_value(line.item, count.warehouse) / system_quantity, COST
                )
            movement = _post_movement(
                StockMovement.Type.COUNT_GAIN,
                line.item,
                count.warehouse,
                variance,
                unit_cost=unit_cost,
                batch=line.batch,
                reference=count.number,
                reason=count.notes,
                actor=actor,
                count_line=line,
            )
            line.unit_cost = movement.unit_cost
        elif variance < 0:
            movement = _post_movement(
                StockMovement.Type.COUNT_LOSS,
                line.item,
                count.warehouse,
                -variance,
                batch=line.batch,
                reference=count.number,
                reason=count.notes,
                actor=actor,
                check_available=False,
                count_line=line,
            )
            line.unit_cost = movement.unit_cost
        line.save(
            update_fields=[
                "system_quantity",
                "variance",
                "unit_cost",
                "updated_at",
            ]
        )
    count.status = StockCount.Status.POSTED
    count.posted_at = timezone.now()
    count.posted_by = actor
    count.save(update_fields=["status", "posted_at", "posted_by", "updated_at"])
    return count


def stock_rows(warehouse=None, item=None) -> list[dict]:
    """Balances derived by summing the ledger, with reservations excluded."""
    movements = StockMovement.objects.all()
    if warehouse is not None:
        movements = movements.filter(warehouse=warehouse)
    if item is not None:
        movements = movements.filter(item=item)
    pairs = (
        movements.values("item_id", "warehouse_id")
        .annotate(on_hand=Sum("quantity"), ledger_value=Sum("value_delta"))
        .order_by("item_id", "warehouse_id")
    )
    reservations = StockReservation.objects.filter(status=StockReservation.Status.OPEN)
    if warehouse is not None:
        reservations = reservations.filter(warehouse=warehouse)
    if item is not None:
        reservations = reservations.filter(item=item)
    reserved = {
        (row["item_id"], row["warehouse_id"]): row["total"] or ZERO
        for row in reservations.values("item_id", "warehouse_id").annotate(
            total=Sum(F("quantity") - F("quantity_fulfilled"))
        )
    }
    items = {
        row.pk: row
        for row in CatalogueItem.objects.filter(pk__in={pair["item_id"] for pair in pairs})
    }
    warehouses = {
        row.pk: row
        for row in Warehouse.objects.filter(pk__in={pair["warehouse_id"] for pair in pairs})
    }

    rows = []
    for pair in pairs:
        on_hand = pair["on_hand"] or ZERO
        value = pair["ledger_value"] or ZERO
        held = reserved.get((pair["item_id"], pair["warehouse_id"]), ZERO)
        if on_hand == 0 and value == 0:
            continue
        rows.append(
            {
                "item_id": pair["item_id"],
                "item_code": items[pair["item_id"]].code,
                "item_name": items[pair["item_id"]].name,
                "warehouse_id": pair["warehouse_id"],
                "warehouse_code": warehouses[pair["warehouse_id"]].code,
                "on_hand": _quantize(on_hand, QTY),
                "reserved": _quantize(held, QTY),
                "available": _quantize(on_hand - held, QTY),
                "unit_cost": _quantize(value / on_hand, COST) if on_hand else ZERO,
                "value": _quantize(value, CENT),
            }
        )
    return rows


def valuation_rows(warehouse=None, item=None) -> dict:
    method = valuation_method()
    rows = stock_rows(warehouse=warehouse, item=item)
    if method == InventoryPolicy.Method.FIFO:
        for row in rows:
            layers = StockLayer.objects.filter(
                item_id=row["item_id"], warehouse_id=row["warehouse_id"]
            )
            value = sum((layer.remaining_quantity * layer.unit_cost for layer in layers), ZERO)
            row["value"] = _quantize(value, CENT)
            if row["on_hand"]:
                row["unit_cost"] = _quantize(row["value"] / row["on_hand"], COST)
    total_quantity = sum((row["on_hand"] for row in rows), ZERO)
    total_value = sum((row["value"] for row in rows), ZERO)
    return {
        "method": method,
        "rows": rows,
        "total_quantity": _quantize(total_quantity, QTY),
        "total_value": _quantize(total_value, CENT),
    }


def reorder_alerts() -> list[dict]:
    alerts = []
    levels = ReorderLevel.objects.filter(is_active=True).select_related("item", "warehouse")
    for level in levels:
        on_hand = _on_hand(level.item, level.warehouse)
        held = _reserved(level.item, level.warehouse)
        if on_hand > level.minimum_quantity:
            continue
        alerts.append(
            {
                "reorder_level_id": level.pk,
                "item_id": level.item_id,
                "item_code": level.item.code,
                "item_name": level.item.name,
                "warehouse_id": level.warehouse_id,
                "warehouse_code": level.warehouse.code,
                "minimum_quantity": _quantize(level.minimum_quantity, QTY),
                "reorder_quantity": _quantize(level.reorder_quantity, QTY),
                "on_hand": _quantize(on_hand, QTY),
                "reserved": _quantize(held, QTY),
                "available": _quantize(on_hand - held, QTY),
                "shortfall": _quantize(level.minimum_quantity - on_hand, QTY),
            }
        )
    return alerts
