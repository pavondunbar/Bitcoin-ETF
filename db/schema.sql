CREATE TABLE journal_entries (
    id UUID PRIMARY KEY,
    account TEXT NOT NULL,
    debit NUMERIC,
    credit NUMERIC,
    created_at TIMESTAMPTZ DEFAULT now(),

    CHECK (
        (debit IS NOT NULL AND credit IS NULL)
        OR
        (credit IS NOT NULL AND debit IS NULL)
    )
);

-- =========================================================
-- EVENT SOURCING LAYER (APPEND-ONLY EVENT LOG)
-- =========================================================
CREATE TABLE event_log (
    id UUID PRIMARY KEY,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,

    -- critical for replay + deduplication
    idempotency_key TEXT UNIQUE,

    created_at TIMESTAMPTZ DEFAULT now()
);

-- Index for replay performance (VERY IMPORTANT once it grows)
CREATE INDEX idx_event_log_created_at
ON event_log (created_at);

CREATE INDEX idx_event_log_event_type
ON event_log (event_type);

-- =========================================================
-- DERIVED READ MODEL (NO MUTABLE STATE)
-- =========================================================
CREATE VIEW account_balances AS
SELECT
    account,
    SUM(COALESCE(debit, 0) - COALESCE(credit, 0)) AS balance
FROM journal_entries
GROUP BY account;
