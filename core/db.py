import os
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone


# ------------------------------------------------------------
# DATABASE CONFIG
# ------------------------------------------------------------

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "ccp"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
}


# ------------------------------------------------------------
# CONNECTION HANDLER
# ------------------------------------------------------------

def get_conn():
    """
    Creates a new Postgres connection.
    In production you'd pool this (PgBouncer / SQLAlchemy pool).
    """
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)


# ------------------------------------------------------------
# INIT DATABASE (RUN ON STARTUP)
# ------------------------------------------------------------

def init_db():
    """
    Ensures required tables exist.
    Safe to run multiple times.
    """
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS journal_entries (
        id UUID PRIMARY KEY,
        event_type TEXT NOT NULL,
        account TEXT NOT NULL,
        debit NUMERIC,
        credit NUMERIC,
        payload JSONB,
        created_at TIMESTAMP DEFAULT now(),

        CHECK (
            (debit IS NOT NULL AND credit IS NULL)
            OR
            (credit IS NOT NULL AND debit IS NULL)
        )
    );
    """)

    conn.commit()
    cur.close()
    conn.close()


# ------------------------------------------------------------
# CORE LEDGER WRITE (APPEND ONLY)
# ------------------------------------------------------------

def write_journal_entry(
    event_type: str,
    account: str,
    debit: float = None,
    credit: float = None,
    payload: dict = None,
):
    """
    Append-only ledger write.
    This is the ONLY way data enters your system.
    """

    conn = get_conn()
    cur = conn.cursor()

    entry_id = str(uuid.uuid4())

    cur.execute("""
        INSERT INTO journal_entries (
            id,
            event_type,
            account,
            debit,
            credit,
            payload,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        entry_id,
        event_type,
        account,
        debit,
        credit,
        payload or {},
        datetime.now(timezone.utc),
    ))

    conn.commit()
    cur.close()
    conn.close()

    return entry_id


# ------------------------------------------------------------
# READ LEDGER STATE
# ------------------------------------------------------------

def get_account_balance(account: str):
    """
    Derived balance (DO NOT store balance state).
    """
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0) AS balance
        FROM journal_entries
        WHERE account = %s
    """, (account,))

    result = cur.fetchone()
    cur.close()
    conn.close()

    return float(result["balance"])


# ------------------------------------------------------------
# FETCH RECENT EVENTS (FOR DEBUG / REPLAY)
# ------------------------------------------------------------

def get_recent_events(limit: int = 50):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM journal_entries
        ORDER BY created_at DESC
        LIMIT %s
    """, (limit,))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return rows


# ------------------------------------------------------------
# HEALTH CHECK
# ------------------------------------------------------------

def health_check():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        cur.fetchone()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB HEALTH ERROR] {e}")
        return False
