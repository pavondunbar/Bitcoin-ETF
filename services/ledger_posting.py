from uuid import uuid4
from datetime import datetime, timezone

from core.db import get_conn
from events.events import Event, EventType


# ------------------------------------------------------------
# ACCOUNT MAPPING (simplified CCP-style mapping layer)
# ------------------------------------------------------------
def get_accounts(event: Event):
    """Deterministic accounting rules based on event type."""

    payload = event.payload

    if event.type == EventType.SETTLEMENT_CONFIRMED:
        return {
            "debit_account": "clearing.cash_obligation",
            "credit_account": "clearing.etf_inventory",
            "amount": payload.get("nav", 0),
        }

    if event.type == EventType.NETTING_EXECUTED:
        return {
            "debit_account": "netting.exposure",
            "credit_account": "netting.offset",
            "amount": payload.get("net_qty", 0),
        }

    if event.type == EventType.TRADE_CREATED:
        return {
            "debit_account": "trade.receivable",
            "credit_account": "trade.payable",
            "amount": payload.get("nav", 0),
        }

    # ignore non-accounting events
    return None


# ------------------------------------------------------------
# JOURNAL ENTRY WRITER (with audit context)
# ------------------------------------------------------------
def insert_journal_entry(
    conn, account, debit=None, credit=None,
    request_id=None, trace_id=None, actor=None,
):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO journal_entries
                (id, account, debit, credit,
                 request_id, trace_id, actor, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid4()),
                account,
                debit,
                credit,
                request_id,
                trace_id,
                actor,
                datetime.now(timezone.utc),
            ),
        )


# ------------------------------------------------------------
# EVENT HANDLER
# ------------------------------------------------------------
def ledger_posting_handler(bus):
    """Subscribes to events and writes accounting entries."""

    def handle(event: Event):
        mapping = get_accounts(event)

        if not mapping:
            return  # non-financial event

        conn = get_conn()

        amount = mapping["amount"]

        # Extract audit context from event
        request_id = getattr(event, "request_id", None)
        trace_id = getattr(event, "trace_id", None)
        actor = getattr(event, "actor", None)

        print(
            f"[LEDGER] Posting for {event.type} "
            f"(trace={trace_id}, actor={actor})"
        )

        # Double-entry: debit + credit with audit trail
        insert_journal_entry(
            conn, mapping["debit_account"],
            debit=amount, credit=None,
            request_id=request_id,
            trace_id=trace_id,
            actor=actor,
        )
        insert_journal_entry(
            conn, mapping["credit_account"],
            debit=None, credit=amount,
            request_id=request_id,
            trace_id=trace_id,
            actor=actor,
        )

        conn.commit()
        conn.close()

    return handle
