# Banking and reconciliation manual

## 1. Account setup

Create company bank accounts with a unique code, bank name, masked account number, currency and classification. Only the last four digits are stored. Link the account to an approved GL account; without this link the cash-flow statement and GL cash balance are unavailable.

Supplier and customer bank details are separate master data. Changes to supplier bank details use the bank-change request control and must not be made silently.

## 2. Statements

1. Obtain the official CSV/XLSX statement.
2. Create a statement record with account, period, opening and closing balances.
3. Import the file using the agreed column mapping.
4. The system checks the file fingerprint to prevent importing the same statement twice.
5. Review imported lines and the duplicate status.
6. Investigate unmatched, duplicate and excluded lines.

The recorded statement opening/closing balance must agree with the source. Do not type a balancing figure.

## 3. Matching

Match statement lines to company bank transactions. Support one-to-one and approved split matching. A match cannot exceed the available line/transaction amount. Record a note for partial or split matches.

If a line is not a company transaction, exclude it with a written investigation reason. Do not exclude an item simply to make the reconciliation balance.

## 4. Reconciliation

1. Confirm all lines are matched or excluded.
2. Confirm the statement closing balance agrees to the reconciled balance.
3. Submit for independent approval.
4. Approval creates the controlled reconciliation record.

A reconciliation marked pending is not final. Book balances and statement balances are different measures; the latest reconciled statement is the confirmed bank position.

## 5. Transfers and cash

Bank transfers are recorded between company accounts with maker-checker control. The platform does not send instructions to a bank. Petty-cash vouchers and replenishments are recorded; physical cash counts remain a manual control.

## 6. Exceptions

Escalate:

- duplicate statement lines;
- payments in the bank with no book entry;
- book entries not on the statement beyond an agreed timing window;
- changed supplier bank details;
- reconciliation differences that cannot be explained.

## 7. Reports

**Reports → Banking** shows accounts, recorded movements, reconciliation status, statements and cash accounts. It is a book record, not a live bank feed.
