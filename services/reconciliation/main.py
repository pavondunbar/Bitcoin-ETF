import uuid
from datetime import datetime, timezone
from collections import defaultdict

from core.db import get_conn


def run_reconciliation():
    """
    RECONCILIATION ENGINE

    Flow:
    1. Replay all journal entries → recompute expected balances
    2. Read account_balances view (current derived state)
    3. Compare expected vs actual per account
    4. Record results to reconciliation_results table
    5. Alert on any mismatch

    This is the primary control ensuring ledger integrity.
    Any discrepancy means data corruption or logic error.
    """
    run_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc)

    print(f"\n[RECONCILIATION] Starting run {run_id}")
    print(f"[RECONCILIATION] Timestamp: {timestamp.isoformat()}")

    conn = get_conn()
    cur = conn.cursor()

    # ==========================================================
    # STEP 1: REPLAY — recompute balances from raw entries
    # ==========================================================
    cur.execute("""
        SELECT
            account,
            SUM(COALESCE(debit, 0)) AS total_debits,
            SUM(COALESCE(credit, 0)) AS total_credits,
            COUNT(*) AS entry_count
        FROM journal_entries
        GROUP BY account
        ORDER BY account
    """)

    replayed = {}
    total_entries = 0

    for row in cur.fetchall():
        account = row["account"]
        debits = float(row["total_debits"])
        credits = float(row["total_credits"])
        count = row["entry_count"]
        total_entries += count

        replayed[account] = {
            "balance": debits - credits,
            "debits": debits,
            "credits": credits,
            "entries": count,
        }

    print(
        f"[RECONCILIATION] Replayed {total_entries} entries "
        f"across {len(replayed)} accounts"
    )

    # ==========================================================
    # STEP 2: READ — get current derived balances from view
    # ==========================================================
    cur.execute("SELECT account, balance FROM account_balances")

    actual = {}
    for row in cur.fetchall():
        actual[row["account"]] = float(row["balance"])

    # ==========================================================
    # STEP 3: COMPARE — detect mismatches
    # ==========================================================
    all_accounts = set(replayed.keys()) | set(actual.keys())

    mismatches = []
    matches = 0

    for account in sorted(all_accounts):
        expected = replayed.get(account, {}).get("balance", 0.0)
        current = actual.get(account, 0.0)
        difference = abs(expected - current)

        # Tolerance for floating-point (8 decimal places)
        if difference > 1e-8:
            status = "MISMATCH"
            mismatches.append({
                "account": account,
                "expected": expected,
                "actual": current,
                "difference": difference,
            })
        else:
            status = "MATCH"
            matches += 1

        # Record every comparison
        cur.execute(
            """
            INSERT INTO reconciliation_results
                (id, run_id, account, expected_balance,
                 actual_balance, difference, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid.uuid4()),
                run_id,
                account,
                expected,
                current,
                difference,
                status,
                timestamp,
            ),
        )

    conn.commit()

    # ==========================================================
    # STEP 4: GLOBAL INVARIANT — total debits must equal credits
    # ==========================================================
    cur.execute("""
        SELECT
            COALESCE(SUM(debit), 0) AS total_debits,
            COALESCE(SUM(credit), 0) AS total_credits
        FROM journal_entries
    """)

    totals = cur.fetchone()
    total_debits = float(totals["total_debits"])
    total_credits = float(totals["total_credits"])
    global_imbalance = abs(total_debits - total_credits)

    cur.close()
    conn.close()

    # ==========================================================
    # STEP 5: REPORT
    # ==========================================================
    print(f"\n{'=' * 60}")
    print(f"  RECONCILIATION REPORT — Run {run_id[:8]}...")
    print(f"{'=' * 60}")
    print(f"  Accounts checked:    {len(all_accounts)}")
    print(f"  Matches:             {matches}")
    print(f"  Mismatches:          {len(mismatches)}")
    print(f"  Total debits:        {total_debits:,.2f}")
    print(f"  Total credits:       {total_credits:,.2f}")
    print(f"  Global imbalance:    {global_imbalance:,.8f}")

    if mismatches:
        print(f"\n  *** ALERT: {len(mismatches)} MISMATCHES ***")
        for m in mismatches:
            print(
                f"    {m['account']}: "
                f"expected={m['expected']:,.8f} "
                f"actual={m['actual']:,.8f} "
                f"diff={m['difference']:,.8f}"
            )

    if global_imbalance > 1e-8:
        print(
            f"\n  *** CRITICAL: GLOBAL DEBIT/CREDIT IMBALANCE "
            f"of {global_imbalance:,.8f} ***"
        )

    if not mismatches and global_imbalance <= 1e-8:
        print("\n  RESULT: ALL ACCOUNTS RECONCILED")

    print(f"{'=' * 60}\n")

    return {
        "run_id": run_id,
        "accounts": len(all_accounts),
        "matches": matches,
        "mismatches": len(mismatches),
        "mismatch_details": mismatches,
        "total_debits": total_debits,
        "total_credits": total_credits,
        "global_imbalance": global_imbalance,
        "status": "PASS" if not mismatches else "FAIL",
    }


if __name__ == "__main__":
    result = run_reconciliation()
    exit_code = 0 if result["status"] == "PASS" else 1
    raise SystemExit(exit_code)
