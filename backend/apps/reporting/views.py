"""Read-only reporting API.

Every report is computed on the server. The browser receives rows and never
recalculates a total, so a stale dashboard cannot disagree with the ledger.
"""

from __future__ import annotations

import csv
import io
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounting.models import Account
from apps.accounting.services import Conflict
from apps.core.models import create_audit_event
from apps.reporting.services import report_payload
from shared.exceptions import error_response

from .models import ReportExport

REPORT_NAMES = {
    "overview",
    "financial-statements",
    "cash-flow",
    "trial-balance",
    "general-ledger",
    "journal-register",
    "receivables-ageing",
    "payables-ageing",
    "procurement",
    "inventory",
    "projects",
    "operations",
    "banking",
    "tax",
    "periods",
}

TITLES = {
    "overview": "Executive overview",
    "financial-statements": "Financial statements",
    "cash-flow": "Cash flow statement",
    "trial-balance": "Trial balance",
    "general-ledger": "General ledger",
    "journal-register": "Journal register",
    "receivables-ageing": "Accounts receivable ageing",
    "payables-ageing": "Accounts payable ageing",
    "procurement": "Procurement report",
    "inventory": "Inventory report",
    "projects": "Project performance",
    "operations": "Services and equipment report",
    "banking": "Banking report",
    "tax": "Tax report",
    "periods": "Financial periods",
}

FINANCIAL_REPORTS = {"overview", "financial-statements", "cash-flow", "tax", "periods"}


class UnknownReport(Exception):
    """A report name outside the published reporting surface."""


def _require_report_access(user, name: str, *, export: bool = False) -> None:
    if not user.has_perm("reporting.view_reporting"):
        raise PermissionDenied("You do not have permission to view reports.")
    if name in FINANCIAL_REPORTS and not user.has_perm("reporting.view_financialreporting"):
        raise PermissionDenied("You do not have permission to view financial reports.")
    if export and not user.has_perm("reporting.export_reporting"):
        raise PermissionDenied("You do not have permission to export reports.")


def _dates(request) -> tuple[date, date]:
    today = timezone.localdate()
    start_raw = (request.query_params.get("start") or "").strip()
    end_raw = (request.query_params.get("end") or "").strip()
    try:
        end = date.fromisoformat(end_raw) if end_raw else today
        start = date.fromisoformat(start_raw) if start_raw else end.replace(day=1)
    except ValueError as exc:
        raise ValueError("Dates must use YYYY-MM-DD.") from exc
    if end < start:
        raise ValueError("The end date cannot precede the start date.")
    if (end - start) > timedelta(days=366 * 5):
        raise ValueError("Choose a reporting range of five years or less.")
    return start, end


def _payload(request, name: str) -> dict:
    if name not in REPORT_NAMES:
        raise UnknownReport("Unknown report.")
    start, end = _dates(request)
    account = None
    if name == "general-ledger":
        raw = (request.query_params.get("account") or "").strip()
        if not raw:
            raise ValueError("Choose an account for the general ledger.")
        account = Account.objects.filter(pk=raw).first()
        if account is None:
            raise UnknownReport("Unknown account.")
    return report_payload(name, start, end, account=account)


class ReportView(APIView):
    def get(self, request, name: str):
        _require_report_access(request.user, name)
        try:
            payload = _payload(request, name)
        except UnknownReport as exc:
            return error_response("not_found", str(exc), status.HTTP_404_NOT_FOUND)
        except (ValueError, Conflict) as exc:
            return error_response("invalid_filter", str(exc), status.HTTP_400_BAD_REQUEST)
        return Response(payload)


def _leaf_rows(value, path=""):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _leaf_rows(item, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        if not value:
            yield path, ""
            return
        for index, item in enumerate(value, start=1):
            yield from _leaf_rows(item, f"{path}[{index}]")
    else:
        yield path, "" if value is None else str(value)


def _csv_safe(value: str) -> str:
    """Prevent spreadsheet formula execution without altering real numbers."""

    text = str(value)
    if text.startswith(("\t", "\r", "\n")):
        return "'" + text
    if text.startswith(("=", "+", "@")):
        return "'" + text
    if text.startswith("-"):
        try:
            Decimal(text)
        except InvalidOperation:
            return "'" + text
    return text


class ReportExportView(APIView):
    def get(self, request, name: str):
        _require_report_access(request.user, name, export=True)
        try:
            payload = _payload(request, name)
        except UnknownReport as exc:
            return error_response("not_found", str(exc), status.HTTP_404_NOT_FOUND)
        except (ValueError, Conflict) as exc:
            return error_response("invalid_filter", str(exc), status.HTTP_400_BAD_REQUEST)

        # ``format`` is reserved by DRF for renderer negotiation; using another
        # name avoids content negotiation turning a valid export into a 404.
        export_format = (request.query_params.get("output") or "csv").lower()
        if export_format not in {"csv", "pdf"}:
            return error_response(
                "invalid_filter", "output must be csv or pdf.", status.HTTP_400_BAD_REQUEST
            )
        title = TITLES[name]
        create_audit_event(
            actor=request.user,
            action="report.exported",
            entity_type="reporting.report",
            entity_id=0,
            after={
                "report": name,
                "start": payload.get("start", ""),
                "end": payload.get("end", ""),
                "format": export_format,
            },
            request=request,
        )
        ReportExport.objects.create(
            report_name=name,
            export_format=export_format,
            parameters={
                "start": payload.get("start", ""),
                "end": payload.get("end", ""),
            },
            exported_by=request.user,
        )
        if export_format == "csv":
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(["Report", title])
            writer.writerow(["Generated at", timezone.now().isoformat()])
            writer.writerow(["Path", "Value"])
            for path, value in _leaf_rows(payload):
                writer.writerow([_csv_safe(path), _csv_safe(value)])
            response = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = f'attachment; filename="{name}.csv"'
            return response

        buffer = io.BytesIO()
        document = SimpleDocTemplate(
            buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm
        )
        styles = getSampleStyleSheet()
        story = [
            Paragraph(f"Tico McDon Limited — {title}", styles["Title"]),
            Paragraph(
                f"Generated {timezone.localtime():%Y-%m-%d %H:%M} · source values preserved; "
                "amounts are NGN unless stated otherwise.",
                styles["Normal"],
            ),
            Spacer(1, 6 * mm),
        ]
        leaf_rows = list(_leaf_rows(payload))
        rows = [
            [Paragraph(path[:120], styles["BodyText"]), Paragraph(value[:500], styles["BodyText"])]
            for path, value in leaf_rows
        ][:2000]
        table = Table(rows, colWidths=[90 * mm, 78 * mm], repeatRows=0)
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                ]
            )
        )
        if len(leaf_rows) > 2000:
            story.append(
                Paragraph(
                    f"TRUNCATED: this PDF shows the first 2,000 of {len(leaf_rows):,} values. "
                    "Use the CSV export for the complete dataset.",
                    styles["BodyText"],
                )
            )
            story.append(Spacer(1, 3 * mm))
        story.append(table)
        document.build(story)
        response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{name}.pdf"'
        return response
