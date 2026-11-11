from __future__ import annotations

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalogue.models import CatalogueItem
from apps.inventory.models import (
    InventoryPolicy,
    ReorderLevel,
    StockAdjustment,
    StockCount,
    StockDamage,
    StockIssue,
    StockMovement,
    StockReceipt,
    StockReservation,
    StockReturn,
    StockTransfer,
)
from apps.inventory.serializers import (
    InventoryPolicySerializer,
    ReorderLevelSerializer,
    StockAdjustmentCreateSerializer,
    StockAdjustmentSerializer,
    StockCountCreateSerializer,
    StockCountSerializer,
    StockDamageCreateSerializer,
    StockDamageSerializer,
    StockIssueCreateSerializer,
    StockIssueSerializer,
    StockMovementSerializer,
    StockReceiptCreateSerializer,
    StockReceiptSerializer,
    StockReservationSerializer,
    StockReturnCreateSerializer,
    StockReturnSerializer,
    StockTransferCreateSerializer,
    StockTransferSerializer,
)
from apps.inventory.services import (
    Conflict,
    PolicyNotConfigured,
    cancel_transfer,
    create_count,
    create_transfer,
    dispatch_transfer,
    post_adjustment,
    post_count,
    post_damage,
    post_issue,
    post_return,
    post_stock_receipt,
    receive_transfer,
    release_reservation,
    reorder_alerts,
    reserve_stock,
    set_policy,
    stock_rows,
    valuation_rows,
)
from apps.warehousing.models import Warehouse
from shared.exceptions import error_response
from shared.viewsets import NoDeleteViewSet

RECEIVE = "inventory.receive_stock"
TRANSFER = "inventory.transfer_stock"
ISSUE = "inventory.issue_stock"
RETURN = "inventory.return_stock"
ADJUST = "inventory.adjust_stock"
WRITE_OFF = "inventory.write_off_stock"
COUNT = "inventory.count_stock"
RESERVE = "inventory.reserve_stock"
POLICY = "inventory.set_valuation_method"


def _require(request, permission: str) -> None:
    if not request.user.has_perm(permission):
        raise PermissionDenied("You do not have permission for this action.")


def _conflict(exc: Conflict) -> Response:
    return error_response("invalid_state", str(exc), status.HTTP_409_CONFLICT)


def _object_id(request, key: str):
    raw = (request.query_params.get(key) or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer.") from exc


class InventoryPolicyView(APIView):
    def get(self, request):
        return Response(InventoryPolicySerializer(InventoryPolicy.load()).data)

    def patch(self, request):
        _require(request, POLICY)
        method = (request.data.get("method") or "").strip()
        note = (request.data.get("note") or "").strip()
        try:
            record = set_policy(method, request.user, note)
        except Conflict as exc:
            return _conflict(exc)
        return Response(InventoryPolicySerializer(record).data)


class StockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StockMovementSerializer

    def get_queryset(self):
        queryset = StockMovement.objects.select_related(
            "item", "warehouse", "batch", "serial", "project", "cost_centre"
        ).all()
        filters = {
            "item": "item_id",
            "warehouse": "warehouse_id",
            "movement_type": "movement_type",
            "project": "project_id",
            "reference": "reference",
        }
        for param, field in filters.items():
            value = (self.request.query_params.get(param) or "").strip()
            if value:
                queryset = queryset.filter(**{field: value})
        return queryset


class StockBalanceView(APIView):
    def get(self, request):
        try:
            item_id = _object_id(request, "item")
            warehouse_id = _object_id(request, "warehouse")
        except ValueError as exc:
            return error_response("invalid_filter", str(exc), status.HTTP_400_BAD_REQUEST)
        item = CatalogueItem.objects.filter(pk=item_id).first() if item_id else None
        warehouse = Warehouse.objects.filter(pk=warehouse_id).first() if warehouse_id else None
        if item_id and item is None:
            return error_response("not_found", "Unknown item.", status.HTTP_404_NOT_FOUND)
        if warehouse_id and warehouse is None:
            return error_response("not_found", "Unknown warehouse.", status.HTTP_404_NOT_FOUND)
        rows = stock_rows(warehouse=warehouse, item=item)
        return Response(
            {
                "rows": [
                    {
                        **row,
                        "on_hand": str(row["on_hand"]),
                        "reserved": str(row["reserved"]),
                        "available": str(row["available"]),
                        "unit_cost": str(row["unit_cost"]),
                        "value": str(row["value"]),
                    }
                    for row in rows
                ],
                "total_quantity": str(sum((row["on_hand"] for row in rows), start=0)),
                "total_value": str(sum((row["value"] for row in rows), start=0)),
            }
        )


class InventoryValuationView(APIView):
    def get(self, request):
        try:
            item_id = _object_id(request, "item")
            warehouse_id = _object_id(request, "warehouse")
        except ValueError as exc:
            return error_response("invalid_filter", str(exc), status.HTTP_400_BAD_REQUEST)
        item = CatalogueItem.objects.filter(pk=item_id).first() if item_id else None
        warehouse = Warehouse.objects.filter(pk=warehouse_id).first() if warehouse_id else None
        try:
            report = valuation_rows(warehouse=warehouse, item=item)
        except PolicyNotConfigured as exc:
            return _conflict(exc)
        report["rows"] = [
            {
                **row,
                "on_hand": str(row["on_hand"]),
                "reserved": str(row["reserved"]),
                "available": str(row["available"]),
                "unit_cost": str(row["unit_cost"]),
                "value": str(row["value"]),
            }
            for row in report["rows"]
        ]
        report["total_quantity"] = str(report["total_quantity"])
        report["total_value"] = str(report["total_value"])
        return Response(report)


class ReorderLevelViewSet(NoDeleteViewSet):
    queryset = ReorderLevel.objects.select_related("item", "warehouse").all()
    serializer_class = ReorderLevelSerializer


class ReorderAlertView(APIView):
    def get(self, request):
        return Response(
            [
                {
                    **alert,
                    "minimum_quantity": str(alert["minimum_quantity"]),
                    "reorder_quantity": str(alert["reorder_quantity"]),
                    "on_hand": str(alert["on_hand"]),
                    "reserved": str(alert["reserved"]),
                    "available": str(alert["available"]),
                    "shortfall": str(alert["shortfall"]),
                }
                for alert in reorder_alerts()
            ]
        )


class ReadCreateViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Create-and-read documents; no update or delete route exists."""


class StockReceiptViewSet(ReadCreateViewSet):
    queryset = StockReceipt.objects.select_related(
        "warehouse", "supplier", "received_by"
    ).prefetch_related("lines")

    def get_serializer_class(self):
        return StockReceiptCreateSerializer if self.action == "create" else StockReceiptSerializer

    def create(self, request, *args, **kwargs):
        _require(request, RECEIVE)
        payload = self.get_serializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            receipt = post_stock_receipt(actor=request.user, **payload.validated_data)
        except Conflict as exc:
            return _conflict(exc)
        return Response(StockReceiptSerializer(receipt).data, status=status.HTTP_201_CREATED)


class StockTransferViewSet(ReadCreateViewSet):
    queryset = StockTransfer.objects.select_related(
        "from_warehouse", "to_warehouse", "from_location", "to_location"
    ).prefetch_related("lines")

    def get_serializer_class(self):
        return StockTransferCreateSerializer if self.action == "create" else StockTransferSerializer

    def create(self, request, *args, **kwargs):
        _require(request, TRANSFER)
        payload = self.get_serializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            transfer = create_transfer(actor=request.user, **payload.validated_data)
        except Conflict as exc:
            return _conflict(exc)
        return Response(StockTransferSerializer(transfer).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="dispatch")
    def dispatch_transfer(self, request, pk=None):
        _require(request, TRANSFER)
        try:
            transfer = dispatch_transfer(self.get_object(), request.user)
        except Conflict as exc:
            return _conflict(exc)
        return Response(StockTransferSerializer(self.get_queryset().get(pk=transfer.pk)).data)

    @action(detail=True, methods=["post"])
    def receive(self, request, pk=None):
        _require(request, TRANSFER)
        try:
            transfer = receive_transfer(self.get_object(), request.user)
        except Conflict as exc:
            return _conflict(exc)
        return Response(StockTransferSerializer(self.get_queryset().get(pk=transfer.pk)).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        _require(request, TRANSFER)
        try:
            transfer = cancel_transfer(self.get_object(), request.user)
        except Conflict as exc:
            return _conflict(exc)
        return Response(StockTransferSerializer(self.get_queryset().get(pk=transfer.pk)).data)


class StockIssueViewSet(ReadCreateViewSet):
    queryset = StockIssue.objects.select_related(
        "project", "cost_centre", "issued_by"
    ).prefetch_related("lines")

    def get_serializer_class(self):
        return StockIssueCreateSerializer if self.action == "create" else StockIssueSerializer

    def create(self, request, *args, **kwargs):
        _require(request, ISSUE)
        payload = self.get_serializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            issue = post_issue(actor=request.user, **payload.validated_data)
        except Conflict as exc:
            return _conflict(exc)
        return Response(StockIssueSerializer(issue).data, status=status.HTTP_201_CREATED)


class StockReturnViewSet(ReadCreateViewSet):
    queryset = StockReturn.objects.select_related("project", "returned_by").prefetch_related(
        "lines"
    )

    def get_serializer_class(self):
        return StockReturnCreateSerializer if self.action == "create" else StockReturnSerializer

    def create(self, request, *args, **kwargs):
        _require(request, RETURN)
        payload = self.get_serializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            document = post_return(actor=request.user, **payload.validated_data)
        except Conflict as exc:
            return _conflict(exc)
        return Response(StockReturnSerializer(document).data, status=status.HTTP_201_CREATED)


class StockAdjustmentViewSet(ReadCreateViewSet):
    queryset = StockAdjustment.objects.select_related("adjusted_by").prefetch_related("lines")

    def get_serializer_class(self):
        return (
            StockAdjustmentCreateSerializer
            if self.action == "create"
            else StockAdjustmentSerializer
        )

    def create(self, request, *args, **kwargs):
        _require(request, ADJUST)
        payload = self.get_serializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            document = post_adjustment(actor=request.user, **payload.validated_data)
        except Conflict as exc:
            return _conflict(exc)
        return Response(StockAdjustmentSerializer(document).data, status=status.HTTP_201_CREATED)


class StockDamageViewSet(ReadCreateViewSet):
    queryset = StockDamage.objects.select_related("recorded_by").prefetch_related("lines")

    def get_serializer_class(self):
        return StockDamageCreateSerializer if self.action == "create" else StockDamageSerializer

    def create(self, request, *args, **kwargs):
        _require(request, WRITE_OFF)
        payload = self.get_serializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            document = post_damage(actor=request.user, **payload.validated_data)
        except Conflict as exc:
            return _conflict(exc)
        return Response(StockDamageSerializer(document).data, status=status.HTTP_201_CREATED)


class StockCountViewSet(ReadCreateViewSet):
    queryset = StockCount.objects.select_related(
        "warehouse", "counted_by", "posted_by"
    ).prefetch_related("lines")

    def get_serializer_class(self):
        return StockCountCreateSerializer if self.action == "create" else StockCountSerializer

    def create(self, request, *args, **kwargs):
        _require(request, COUNT)
        payload = self.get_serializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            count = create_count(actor=request.user, **payload.validated_data)
        except Conflict as exc:
            return _conflict(exc)
        return Response(StockCountSerializer(count).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="post")
    def post_count(self, request, pk=None):
        _require(request, COUNT)
        try:
            count = post_count(self.get_object(), request.user)
        except Conflict as exc:
            return _conflict(exc)
        return Response(StockCountSerializer(self.get_queryset().get(pk=count.pk)).data)


class StockReservationViewSet(ReadCreateViewSet):
    queryset = StockReservation.objects.select_related("item", "warehouse", "project").all()
    serializer_class = StockReservationSerializer

    def create(self, request, *args, **kwargs):
        _require(request, RESERVE)
        payload = self.get_serializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        try:
            reservation = reserve_stock(
                item=data["item"],
                warehouse=data["warehouse"],
                quantity=data["quantity"],
                project=data.get("project"),
                reference=data.get("reference", ""),
                notes=data.get("notes", ""),
                actor=request.user,
            )
        except Conflict as exc:
            return _conflict(exc)
        return Response(
            StockReservationSerializer(reservation).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"])
    def release(self, request, pk=None):
        _require(request, RESERVE)
        try:
            reservation = release_reservation(self.get_object(), request.user)
        except Conflict as exc:
            return _conflict(exc)
        return Response(StockReservationSerializer(reservation).data)
