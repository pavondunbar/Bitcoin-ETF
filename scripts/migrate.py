from core.db import get_conn


def run():
    conn = get_conn()
    cur = conn.cursor()

    print("[MIGRATION] Starting schema updates...")

    # ---------------------------------------------------------
    # OUTBOX SUPPORT (event_log state tracking)
    # ---------------------------------------------------------
    cur.execute("""
        ALTER TABLE event_log
        ADD COLUMN IF NOT EXISTS processed BOOLEAN DEFAULT FALSE;
    """)

    cur.execute("""
        ALTER TABLE event_log
        ADD COLUMN IF NOT EXISTS processed_at TIMESTAMPTZ;
    """)

    # ---------------------------------------------------------
    # OPTIONAL: ensure idempotency key exists safely
    # ---------------------------------------------------------
    cur.execute("""
        ALTER TABLE event_log
        ADD COLUMN IF NOT EXISTS idempotency_key TEXT;
    """)

    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_event_log_idempotency
        ON event_log(idempotency_key);
    """)

    # ---------------------------------------------------------
    # OUTBOX PERFORMANCE INDEX
    # ---------------------------------------------------------
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_event_log_processed
        ON event_log(processed);
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_event_log_created_at
        ON event_log(created_at);
    """)

    conn.commit()
    cur.close()
    conn.close()

    print("[MIGRATION] Completed successfully")


if __name__ == "__main__":
    run()
