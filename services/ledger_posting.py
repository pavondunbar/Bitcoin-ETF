from uuid import uuid4
from datetime import datetime, timezone

from core.db import get_conn
from events.events import Event, EventType


# ------------------------------------------------------------
# ACCOUNT MAPPING (simplified CCP-style mapping layer)
# ------------------------------------------------------------
def get_accounts(event: Event):
    """
    Deterministic accounting rules based on event type.
    In a real CCP, this becomes a rules engine.
    """

    payload = event.payload

    if event.type == EventType.SETTLEMENT_FINALIZED:
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
# JOURNAL ENTRY WRITER
# ------------------------------------------------------------
def insert_journal_entry(conn, account, debit=None, credit=None):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO journal_entries (id, account, debit, credit, created_at)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                str(uuid4()),
                account,
                debit,
                credit,
                datetime.now(timezone.utc),
            ),
        )


# ------------------------------------------------------------
# EVENT HANDLER
# ------------------------------------------------------------
def ledger_posting_handler(bus):
    """
    Subscribes to events and writes accounting entries.
    """

    def handle(event: Event):
        mapping = get_accounts(event)

        if not mapping:
            return  # non-financial event

        conn = get_conn()

        amount = mapping["amount"]

        print(f"[LEDGER] Posting journal entries for {event.type}")

        # Double-entry: debit + credit
        insert_journal_entry(conn, mapping["debit_account"], debit=amount, credit=None)
        insert_journal_entry(conn, mapping["credit_account"], debit=None, credit=amount)

        conn.commit()
        conn.close()

    return handle
