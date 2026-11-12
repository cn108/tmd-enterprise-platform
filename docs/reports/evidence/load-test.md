# Controlled staging load test

Requests: 400; workers: 16; wall time: 6.50s
Throughput: 61.5 req/s; unexpected errors: 0

| Endpoint | Requests | Errors | Mean ms | p95 ms | Max ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| session | 80 | 0 | 54.9 | 193.3 | 225.6 |
| purchase_orders | 80 | 0 | 441.9 | 681.4 | 737.1 |
| stock_balances | 80 | 0 | 121.7 | 154.8 | 223.0 |
| financial_statements | 80 | 0 | 281.3 | 649.4 | 731.9 |
| inventory_report | 80 | 0 | 387.0 | 471.5 | 556.1 |

Read-only concurrent load against the local Django development server. It measures application and database query cost, not production network or worker capacity.
