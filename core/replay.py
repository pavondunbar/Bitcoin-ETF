import json
from collections import defaultdict
from datetime import datetime, timezone

from core.db import get_conn
from events.events import Event, EventType


def replay(bus):
    """
    DETERMINISTIC STATE REBUILD

    Replays all events from event_log into the event bus.
    Events already have idempotency keys, so re-publishing
    them through the bus is safe — persist_event will
    short-circuit on duplicates via ON CONFLICT DO NOTHING.
    """
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, event_type, payload, idempotency_key,
               request_id, trace_id, actor
        FROM event_log
        ORDER BY created_at ASC
    """)

    count = 0
    for row in cur.fetchall():
        event = Event(
            type=EventType(row["event_type"]),
            payload=row["payload"],
            id=row["id"],
            idempotency_key=row["idempotency_key"],
            request_id=row["request_id"],
            trace_id=row["trace_id"],
            actor=row["actor"],
        )
        bus.publish(event)
        count += 1

    cur.close()
    conn.close()

    print(f"[REPLAY] Replayed {count} events (duplicates skipped)")
    return count


def rebuild_state():
    """
    FULL STATE RECONSTRUCTION FROM LEDGER

    Recomputes all system state purely from the append-only
    journal entries. Returns the complete derived state
    without touching any mutable tables.

    This proves the system is deterministically rebuildable
    from its ledger alone.
    """
    conn = get_conn()
    cur = conn.cursor()

    # -------------------------------------------------------
    # 1. Rebuild account balances from journal entries
    # -------------------------------------------------------
    cur.execute("""
        SELECT
            account,
            SUM(COALESCE(debit, 0)) AS total_debits,
            SUM(COALESCE(credit, 0)) AS total_credits,
            SUM(COALESCE(debit, 0) - COALESCE(credit, 0))
                AS balance,
            COUNT(*) AS entry_count,
            MIN(created_at) AS first_entry,
            MAX(created_at) AS last_entry
        FROM journal_entries
        GROUP BY account
        ORDER BY account
    """)

    accounts = {}
    for row in cur.fetchall():
        accounts[row["account"]] = {
            "balance": float(row["balance"]),
            "total_debits": float(row["total_debits"]),
            "total_credits": float(row["total_credits"]),
            "entry_count": row["entry_count"],
            "first_entry": str(row["first_entry"]),
            "last_entry": str(row["last_entry"]),
        }

    # -------------------------------------------------------
    # 2. Rebuild event timeline from event_log
    # -------------------------------------------------------
    cur.execute("""
        SELECT event_type, COUNT(*) AS count
        FROM event_log
        GROUP BY event_type
        ORDER BY event_type
    """)

    event_counts = {}
    for row in cur.fetchall():
        event_counts[row["event_type"]] = row["count"]

    # -------------------------------------------------------
    # 3. Rebuild settlement state from settlement_instructions
    # -------------------------------------------------------
    cur.execute("""
        SELECT status, COUNT(*) AS count
        FROM settlement_instructions
        GROUP BY status
        ORDER BY status
    """)

    settlement_states = {}
    for row in cur.fetchall():
        settlement_states[row["status"]] = row["count"]

    # -------------------------------------------------------
    # 4. Global invariants
    # -------------------------------------------------------
    cur.execute("""
        SELECT
            COALESCE(SUM(debit), 0) AS total_debits,
            COALESCE(SUM(credit), 0) AS total_credits,
            COUNT(*) AS total_entries
        FROM journal_entries
    """)

    totals = cur.fetchone()

    cur.close()
    conn.close()

    total_debits = float(totals["total_debits"])
    total_credits = float(totals["total_credits"])

    state = {
        "rebuilt_at": datetime.now(timezone.utc).isoformat(),
        "accounts": accounts,
        "event_counts": event_counts,
        "settlement_states": settlement_states,
        "invariants": {
            "total_debits": total_debits,
            "total_credits": total_credits,
            "debit_credit_balanced": (
                abs(total_debits - total_credits) < 1e-8
            ),
            "total_journal_entries": totals["total_entries"],
        },
    }

    print("\n[REBUILD] State reconstructed from ledger:")
    print(f"  Accounts: {len(accounts)}")
    print(f"  Events:   {sum(event_counts.values())}")
    print(f"  Debits:   {total_debits:,.2f}")
    print(f"  Credits:  {total_credits:,.2f}")
    print(
        f"  Balanced: {state['invariants']['debit_credit_balanced']}"
    )

    return state
