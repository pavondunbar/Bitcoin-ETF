-- =========================================================
-- CORE DOUBLE-ENTRY LEDGER (SOURCE OF FINANCIAL TRUTH)
-- =========================================================

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

    -- CRITICAL: prevents duplicate processing in replay / async bus
    idempotency_key TEXT UNIQUE,

    created_at TIMESTAMPTZ DEFAULT now()
);

-- =========================================================
-- SETTLEMENT LAYER (RTGS / CCP CLEARING INSTRUCTIONS)
-- =========================================================

CREATE TABLE settlement_instructions (
    id UUID PRIMARY KEY,

    event_id UUID,
    event_type TEXT NOT NULL,

    counterparty TEXT,
    amount NUMERIC NOT NULL,
    currency TEXT DEFAULT 'USD',

    status TEXT NOT NULL DEFAULT 'PENDING',

    created_at TIMESTAMPTZ DEFAULT now(),
    settled_at TIMESTAMPTZ
);

CREATE INDEX idx_settlement_status
ON settlement_instructions (status);

CREATE INDEX idx_settlement_created_at
ON settlement_instructions (created_at);

-- =========================================================
-- FX EXPOSURE LAYER (MULTI-CURRENCY CCP EXTENSION)
-- =========================================================

CREATE TABLE fx_exposures (
    id UUID PRIMARY KEY,

    account TEXT NOT NULL,

    base_currency TEXT NOT NULL,
    quote_currency TEXT NOT NULL,

    exposure NUMERIC NOT NULL DEFAULT 0,

    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_fx_account
ON fx_exposures (account);

-- =========================================================
-- EVENT LOG PERFORMANCE INDEXES (REPLAY CRITICAL)
-- =========================================================

CREATE INDEX idx_event_log_created_at
ON event_log (created_at);

CREATE INDEX idx_event_log_event_type
ON event_log (event_type);

CREATE INDEX idx_event_log_idempotency
ON event_log (idempotency_key);

-- =========================================================
-- DERIVED READ MODEL (NO MUTABLE STATE)
-- =========================================================

CREATE VIEW account_balances AS
SELECT
    account,
    SUM(COALESCE(debit, 0) - COALESCE(credit, 0)) AS balance
FROM journal_entries
GROUP BY account;
