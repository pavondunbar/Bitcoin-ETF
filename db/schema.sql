-- =========================================================
-- CORE DOUBLE-ENTRY LEDGER (SOURCE OF FINANCIAL TRUTH)
-- =========================================================

CREATE TABLE journal_entries (
    id UUID PRIMARY KEY,
    account TEXT NOT NULL,
    debit NUMERIC,
    credit NUMERIC,

    -- AUDIT TRAIL: who, what, when, traceable
    request_id TEXT,
    trace_id TEXT,
    actor TEXT,

    created_at TIMESTAMPTZ DEFAULT now(),

    CHECK (
        (debit IS NOT NULL AND credit IS NULL)
        OR
        (credit IS NOT NULL AND debit IS NULL)
    )
);

CREATE INDEX idx_journal_created_at
ON journal_entries (created_at);

CREATE INDEX idx_journal_account
ON journal_entries (account);

CREATE INDEX idx_journal_trace_id
ON journal_entries (trace_id);


-- =========================================================
-- EVENT STORE (APPEND-ONLY DOMAIN EVENTS)
-- =========================================================

CREATE TABLE event_log (
    id UUID PRIMARY KEY,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,

    -- CRITICAL: prevents duplicate processing in replay / retries
    idempotency_key TEXT UNIQUE NOT NULL,

    -- AUDIT TRAIL: full traceability for every state transition
    request_id TEXT,
    trace_id TEXT,
    actor TEXT,

    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_event_log_created_at
ON event_log (created_at);

CREATE INDEX idx_event_log_event_type
ON event_log (event_type);

CREATE INDEX idx_event_log_trace_id
ON event_log (trace_id);


-- =========================================================
-- OUTBOX TABLE (DECOUPLE DB → KAFKA)
-- =========================================================

CREATE TABLE outbox (
    id UUID PRIMARY KEY,

    event_id UUID NOT NULL,
    event_type TEXT NOT NULL,

    payload JSONB NOT NULL,

    status TEXT NOT NULL DEFAULT 'PENDING',
    -- PENDING | SENT | FAILED | DLQ

    created_at TIMESTAMPTZ DEFAULT now(),
    sent_at TIMESTAMPTZ,

    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 5,
    last_error TEXT
);

CREATE INDEX idx_outbox_status
ON outbox (status);

CREATE INDEX idx_outbox_created_at
ON outbox (created_at);


-- =========================================================
-- SETTLEMENT LAYER (CCP / RTGS INSTRUCTIONS)
-- =========================================================

CREATE TABLE settlement_instructions (
    id UUID PRIMARY KEY,

    event_id UUID,
    event_type TEXT NOT NULL,

    counterparty TEXT,
    amount NUMERIC NOT NULL,
    currency TEXT DEFAULT 'USD',

    -- DETERMINISTIC STATE MACHINE:
    -- PENDING → APPROVED → SIGNED → BROADCASTED → CONFIRMED
    status TEXT NOT NULL DEFAULT 'PENDING',

    -- MPC SIGNING
    mpc_signature TEXT,
    signer_quorum JSONB,

    -- BLOCKCHAIN RAILS
    tx_hash TEXT,
    block_number BIGINT,
    confirmations INT DEFAULT 0,

    -- AUDIT TRAIL
    request_id TEXT,
    trace_id TEXT,
    actor TEXT,

    created_at TIMESTAMPTZ DEFAULT now(),
    approved_at TIMESTAMPTZ,
    signed_at TIMESTAMPTZ,
    broadcasted_at TIMESTAMPTZ,
    confirmed_at TIMESTAMPTZ
);

CREATE INDEX idx_settlement_status
ON settlement_instructions (status);

CREATE INDEX idx_settlement_created_at
ON settlement_instructions (created_at);

CREATE INDEX idx_settlement_tx_hash
ON settlement_instructions (tx_hash);


-- =========================================================
-- SETTLEMENT STATE HISTORY (IMMUTABLE AUDIT LOG)
-- =========================================================

CREATE TABLE settlement_state_history (
    id UUID PRIMARY KEY,
    settlement_id UUID NOT NULL REFERENCES settlement_instructions(id),
    previous_status TEXT,
    new_status TEXT NOT NULL,
    actor TEXT,
    reason TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_settlement_history_settlement_id
ON settlement_state_history (settlement_id);


-- =========================================================
-- RBAC: API KEYS AND ROLE PERMISSIONS
-- =========================================================

CREATE TABLE api_keys (
    id UUID PRIMARY KEY,
    key_hash TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    -- Roles: admin | approver | trader | auditor | signer | system
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_api_keys_hash
ON api_keys (key_hash);

CREATE TABLE role_permissions (
    id UUID PRIMARY KEY,
    role TEXT NOT NULL,
    resource TEXT NOT NULL,
    action TEXT NOT NULL,
    -- Actions: create | read | approve | sign | publish
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(role, resource, action)
);

CREATE INDEX idx_role_permissions_role
ON role_permissions (role);

-- SEED RBAC PERMISSIONS
INSERT INTO role_permissions (id, role, resource, action) VALUES
    -- admin: full access
    (gen_random_uuid(), 'admin', '*', 'create'),
    (gen_random_uuid(), 'admin', '*', 'read'),
    (gen_random_uuid(), 'admin', '*', 'approve'),
    (gen_random_uuid(), 'admin', '*', 'sign'),
    (gen_random_uuid(), 'admin', '*', 'publish'),
    -- approver: approve settlements and withdrawals
    (gen_random_uuid(), 'approver', 'settlement', 'approve'),
    (gen_random_uuid(), 'approver', 'settlement', 'read'),
    (gen_random_uuid(), 'approver', 'withdrawal', 'approve'),
    (gen_random_uuid(), 'approver', 'trade', 'read'),
    (gen_random_uuid(), 'approver', 'ledger', 'read'),
    -- trader: submit trades, view positions
    (gen_random_uuid(), 'trader', 'trade', 'create'),
    (gen_random_uuid(), 'trader', 'trade', 'read'),
    (gen_random_uuid(), 'trader', 'ledger', 'read'),
    (gen_random_uuid(), 'trader', 'settlement', 'read'),
    -- auditor: read-only across all resources
    (gen_random_uuid(), 'auditor', '*', 'read'),
    -- signer: sign transactions only
    (gen_random_uuid(), 'signer', 'settlement', 'sign'),
    (gen_random_uuid(), 'signer', 'settlement', 'read'),
    -- system: publish events, internal operations
    (gen_random_uuid(), 'system', 'event', 'publish'),
    (gen_random_uuid(), 'system', '*', 'read'),
    (gen_random_uuid(), 'system', 'settlement', 'create');


-- =========================================================
-- RECONCILIATION RESULTS
-- =========================================================

CREATE TABLE reconciliation_results (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL,
    account TEXT NOT NULL,
    expected_balance NUMERIC NOT NULL,
    actual_balance NUMERIC NOT NULL,
    difference NUMERIC NOT NULL,
    status TEXT NOT NULL DEFAULT 'MATCH',
    -- MATCH | MISMATCH | ERROR
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_reconciliation_run_id
ON reconciliation_results (run_id);

CREATE INDEX idx_reconciliation_status
ON reconciliation_results (status);


-- =========================================================
-- FX EXPOSURE LAYER (OPTIONAL EXTENSION)
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
-- IDEMPOTENCY SAFETY (GLOBAL EVENT GUARANTEE)
-- =========================================================

CREATE UNIQUE INDEX idx_event_log_idempotency
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
