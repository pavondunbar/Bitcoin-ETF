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
    # IDEMPOTENCY KEY
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
    # AUDIT TRAIL COLUMNS: event_log
    # ---------------------------------------------------------
    cur.execute("""
        ALTER TABLE event_log
        ADD COLUMN IF NOT EXISTS request_id TEXT;
    """)

    cur.execute("""
        ALTER TABLE event_log
        ADD COLUMN IF NOT EXISTS trace_id TEXT;
    """)

    cur.execute("""
        ALTER TABLE event_log
        ADD COLUMN IF NOT EXISTS actor TEXT;
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_event_log_trace_id
        ON event_log(trace_id);
    """)

    # ---------------------------------------------------------
    # AUDIT TRAIL COLUMNS: journal_entries
    # ---------------------------------------------------------
    cur.execute("""
        ALTER TABLE journal_entries
        ADD COLUMN IF NOT EXISTS request_id TEXT;
    """)

    cur.execute("""
        ALTER TABLE journal_entries
        ADD COLUMN IF NOT EXISTS trace_id TEXT;
    """)

    cur.execute("""
        ALTER TABLE journal_entries
        ADD COLUMN IF NOT EXISTS actor TEXT;
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_journal_trace_id
        ON journal_entries(trace_id);
    """)

    # ---------------------------------------------------------
    # SETTLEMENT: blockchain + MPC columns
    # ---------------------------------------------------------
    cur.execute("""
        ALTER TABLE settlement_instructions
        ADD COLUMN IF NOT EXISTS mpc_signature TEXT;
    """)

    cur.execute("""
        ALTER TABLE settlement_instructions
        ADD COLUMN IF NOT EXISTS signer_quorum JSONB;
    """)

    cur.execute("""
        ALTER TABLE settlement_instructions
        ADD COLUMN IF NOT EXISTS tx_hash TEXT;
    """)

    cur.execute("""
        ALTER TABLE settlement_instructions
        ADD COLUMN IF NOT EXISTS block_number BIGINT;
    """)

    cur.execute("""
        ALTER TABLE settlement_instructions
        ADD COLUMN IF NOT EXISTS confirmations INT DEFAULT 0;
    """)

    cur.execute("""
        ALTER TABLE settlement_instructions
        ADD COLUMN IF NOT EXISTS request_id TEXT;
    """)

    cur.execute("""
        ALTER TABLE settlement_instructions
        ADD COLUMN IF NOT EXISTS trace_id TEXT;
    """)

    cur.execute("""
        ALTER TABLE settlement_instructions
        ADD COLUMN IF NOT EXISTS actor TEXT;
    """)

    cur.execute("""
        ALTER TABLE settlement_instructions
        ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ;
    """)

    cur.execute("""
        ALTER TABLE settlement_instructions
        ADD COLUMN IF NOT EXISTS signed_at TIMESTAMPTZ;
    """)

    cur.execute("""
        ALTER TABLE settlement_instructions
        ADD COLUMN IF NOT EXISTS broadcasted_at TIMESTAMPTZ;
    """)

    cur.execute("""
        ALTER TABLE settlement_instructions
        ADD COLUMN IF NOT EXISTS confirmed_at TIMESTAMPTZ;
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_settlement_tx_hash
        ON settlement_instructions(tx_hash);
    """)

    # ---------------------------------------------------------
    # OUTBOX: DLQ support columns
    # ---------------------------------------------------------
    cur.execute("""
        ALTER TABLE outbox
        ADD COLUMN IF NOT EXISTS max_retries INT DEFAULT 5;
    """)

    cur.execute("""
        ALTER TABLE outbox
        ADD COLUMN IF NOT EXISTS last_error TEXT;
    """)

    # ---------------------------------------------------------
    # NEW TABLES (IF NOT EXISTS)
    # ---------------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settlement_state_history (
            id UUID PRIMARY KEY,
            settlement_id UUID NOT NULL,
            previous_status TEXT,
            new_status TEXT NOT NULL,
            actor TEXT,
            reason TEXT,
            metadata JSONB,
            created_at TIMESTAMPTZ DEFAULT now()
        );
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS
            idx_settlement_history_settlement_id
        ON settlement_state_history(settlement_id);
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id UUID PRIMARY KEY,
            key_hash TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT now()
        );
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_api_keys_hash
        ON api_keys(key_hash);
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS role_permissions (
            id UUID PRIMARY KEY,
            role TEXT NOT NULL,
            resource TEXT NOT NULL,
            action TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE(role, resource, action)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS reconciliation_results (
            id UUID PRIMARY KEY,
            run_id UUID NOT NULL,
            account TEXT NOT NULL,
            expected_balance NUMERIC NOT NULL,
            actual_balance NUMERIC NOT NULL,
            difference NUMERIC NOT NULL,
            status TEXT NOT NULL DEFAULT 'MATCH',
            created_at TIMESTAMPTZ DEFAULT now()
        );
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_reconciliation_run_id
        ON reconciliation_results(run_id);
    """)

    # ---------------------------------------------------------
    # PERFORMANCE INDEXES
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
