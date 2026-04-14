CREATE TABLE journal_entries (
    id UUID PRIMARY KEY,
    account TEXT NOT NULL,
    debit NUMERIC,
    credit NUMERIC,
    created_at TIMESTAMP DEFAULT now(),

    CHECK (
        (debit IS NOT NULL AND credit IS NULL)
        OR
        (credit IS NOT NULL AND debit IS NULL)
    )
);

-- Derived balances ONLY (no mutable state)
CREATE VIEW account_balances AS
SELECT
    account,
    SUM(COALESCE(debit,0) - COALESCE(credit,0)) AS balance
FROM journal_entries
GROUP BY account;
