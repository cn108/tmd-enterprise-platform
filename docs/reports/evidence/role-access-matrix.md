# Role-based access acceptance

Staging database: `tmd_staging`
Roles exercised: 10; checks: 130
All checks passed: **True**

Expected access: allowed actions must not return 403; denied actions must return 403.

| Role | Checks passed |
| --- | ---: |
| System Administrator | 13/13 |
| Management | 13/13 |
| Accountant | 13/13 |
| Finance Controller | 13/13 |
| Finance Officer | 13/13 |
| Procurement Officer | 13/13 |
| Project Manager | 13/13 |
| Storekeeper | 13/13 |
| Operations / HSE | 13/13 |
| Auditor | 13/13 |
