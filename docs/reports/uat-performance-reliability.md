# Performance and reliability report

**Environment:** local Windows workstation, Django development server, PostgreSQL in Docker, staging data.
**Evidence:** `docs/reports/evidence/load-test.json`, `load-test.md`.

## 1. Measured read load

| Measure | Result |
| --- | ---: |
| Concurrent workers | 16 |
| Requests | 400 |
| Wall time | 6.50 s |
| Throughput | 61.5 requests/s |
| Unexpected errors | 0 |

| Endpoint | Requests | Errors | Mean | p95 | Max |
| --- | ---: | ---: | ---: | ---: | ---: |
| Session / current user | 80 | 0 | 54.9 ms | 193.3 ms | 225.6 ms |
| Purchase orders | 80 | 0 | 441.9 ms | 681.4 ms | 737.1 ms |
| Stock balances | 80 | 0 | 121.7 ms | 154.8 ms | 223.0 ms |
| Financial statements (year) | 80 | 0 | 281.3 ms | 649.4 ms | 731.9 ms |
| Inventory report (year) | 80 | 0 | 387.0 ms | 471.5 ms | 556.1 ms |

The financial-statement endpoint returned 40 × 200 and 40 × 403 because the load generator includes operational roles. The 403s are the intended least-privilege result and are not errors.

## 2. Query behaviour

Single-request query counts on the staging data:

| Endpoint | Queries | Database time |
| --- | ---: | ---: |
| Purchase orders | 15 | 57 ms |
| Inventory report | 12 | 51 ms |
| Financial statements | 16 | 51 ms |

There is no runaway N+1 on these paths. The higher purchase-order latency under concurrency is consistent with serialisation and development-server contention. Production must be re-measured behind the real WSGI/ASGI server and connection pool.

## 3. Transaction integrity

The test did **not** trade integrity for throughput. Existing regression suites passed for:
- per-item row locking before stock issues, preventing oversell;
- reservation overlap refusal;
- signed, append-only stock movements;
- idempotent payment recording and replay;
- duplicate invoice rejection and near-duplicate flags;
- approved reconciliation locks and no re-match after approval;
- immutable posted journals and period closure.

All 295 backend tests passed after the permission hardening.

## 4. Reliability observations

| ID | Severity | Finding | Status |
| --- | --- | --- | --- |
| PERF-01 | **Medium** | Purchase-order listing p95 reached 681 ms under 16 concurrent workers on the development server. It is acceptable for small-team UAT but must be re-measured on production workers. | Open |
| PERF-02 | **Medium** | No write-concurrency load was run against staging; write integrity is covered by targeted automated tests, not by a sustained load generator. Running destructive write load safely requires a disposable database and production-like workers. | Open, scope limit |
| PERF-03 | **Medium** | No background worker exists for the tested synchronous workflows. Worker-failure recovery could not be exercised. | Not applicable to current runtime; re-assess before adding queues |
| PERF-04 | **Medium** | Database-interruption and failover behaviour was not simulated. Docker health checks are present, but no application retry/failover test was performed. | Open |
| PERF-05 | **Low** | File-upload throughput was not load-tested. Document size/type limits are enforced by existing tests. | Residual test gap |
| PERF-06 | **Low** | The load test used a development server, not Gunicorn/Uvicorn, a reverse proxy or a production database size. Figures are comparative, not capacity guarantees. | Documented |

## 5. Conclusion

For controlled UAT with a small number of concurrent employees, the measured read paths are responsive and error-free. No transaction-integrity failure was observed. Production capacity, sustained write concurrency, database failover and worker recovery remain unproven and must be re-tested in the target infrastructure.
