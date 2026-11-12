"""Measured concurrent read load against the staging API."""

from __future__ import annotations

import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from rest_framework.test import APIClient

from apps.identity.models import User

STAGING_DB = "tmd_staging"
USERS = [
    "management@staging.tmd.local",
    "accountant@staging.tmd.local",
    "finance@staging.tmd.local",
    "procurement@staging.tmd.local",
    "store@staging.tmd.local",
    "project@staging.tmd.local",
    "operations@staging.tmd.local",
    "auditor@staging.tmd.local",
]
ENDPOINTS = {
    "session": "/api/v1/auth/me/",
    "purchase_orders": "/api/v1/purchase-orders/",
    "stock_balances": "/api/v1/stock-balances/",
    "financial_statements": (
        "/api/v1/reporting/financial-statements/?start=2026-01-01&end=2026-12-31"
    ),
    "inventory_report": "/api/v1/reporting/inventory/?start=2026-01-01&end=2026-12-31",
}


class Command(BaseCommand):
    help = "Run measured concurrent read sessions and report latency and error rates."

    def handle(self, *args, **options):
        if connection.settings_dict["NAME"] != STAGING_DB:
            raise CommandError(f"This command only runs against {STAGING_DB}.")
        users = {email: User.objects.get(email=email) for email in USERS}

        def request(index: int, endpoint: str, url: str):
            email = USERS[index % len(USERS)]
            client = APIClient(HTTP_HOST="localhost")
            client.force_authenticate(users[email])
            started = time.perf_counter()
            try:
                response = client.get(url)
                status = response.status_code
            except Exception as exc:  # noqa: BLE001 - measured failure is evidence
                status = 0
                self.stderr.write(f"{endpoint}: {exc}")
            return endpoint, status, (time.perf_counter() - started) * 1000

        jobs = []
        index = 0
        for _ in range(8):
            for endpoint, url in ENDPOINTS.items():
                for _ in range(10):
                    jobs.append((index, endpoint, url))
                    index += 1

        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(lambda job: request(*job), jobs))
        elapsed = time.perf_counter() - started

        summary = {}
        for endpoint in ENDPOINTS:
            samples = [item for item in results if item[0] == endpoint]
            latencies = sorted(item[2] for item in samples)
            errors = sum(1 for item in samples if item[1] not in (200, 401, 403))
            summary[endpoint] = {
                "requests": len(samples),
                "errors": errors,
                "status_counts": {
                    str(code): sum(1 for item in samples if item[1] == code)
                    for code in sorted({item[1] for item in samples})
                },
                "mean_ms": round(statistics.mean(latencies), 1),
                "p95_ms": round(latencies[max(0, int(len(latencies) * 0.95) - 1)], 1),
                "max_ms": round(max(latencies), 1),
            }
        total_errors = sum(item["errors"] for item in summary.values())
        payload = {
            "database": connection.settings_dict["NAME"],
            "workers": 16,
            "requests": len(results),
            "wall_seconds": round(elapsed, 2),
            "requests_per_second": round(len(results) / elapsed, 1),
            "errors": total_errors,
            "endpoints": summary,
            "note": (
                "Read-only concurrent load against the local Django development server. "
                "It measures application and database query cost, not production network "
                "or worker capacity."
            ),
        }
        evidence = Path(settings.BASE_DIR).parent / "docs" / "reports" / "evidence"
        evidence.mkdir(parents=True, exist_ok=True)
        (evidence / "load-test.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        lines = [
            "# Controlled staging load test",
            "",
            f"Requests: {len(results)}; workers: 16; wall time: {elapsed:.2f}s",
            (
                f"Throughput: {payload['requests_per_second']} req/s; "
                f"unexpected errors: {total_errors}"
            ),
            "",
            "| Endpoint | Requests | Errors | Mean ms | p95 ms | Max ms |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
        for name, row in summary.items():
            lines.append(
                f"| {name} | {row['requests']} | {row['errors']} | {row['mean_ms']} | "
                f"{row['p95_ms']} | {row['max_ms']} |"
            )
        lines += ["", payload["note"]]
        (evidence / "load-test.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.stdout.write(json.dumps(payload, indent=2))
        if total_errors:
            raise CommandError("Unexpected load-test errors; see docs/reports/evidence.")
