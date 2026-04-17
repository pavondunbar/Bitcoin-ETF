CREATE OR REPLACE FUNCTION prevent_mutation()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'APPEND ONLY TABLE - NO UPDATE OR DELETE';
END;
$$ LANGUAGE plpgsql;

-- JOURNAL ENTRIES: fully immutable
CREATE TRIGGER no_update
BEFORE UPDATE ON journal_entries
FOR EACH ROW EXECUTE FUNCTION prevent_mutation();

CREATE TRIGGER no_delete
BEFORE DELETE ON journal_entries
FOR EACH ROW EXECUTE FUNCTION prevent_mutation();

-- EVENT LOG: fully immutable (outbox worker uses separate outbox table)
CREATE TRIGGER no_update_event_log
BEFORE UPDATE ON event_log
FOR EACH ROW EXECUTE FUNCTION prevent_mutation();

CREATE TRIGGER no_delete_event_log
BEFORE DELETE ON event_log
FOR EACH ROW EXECUTE FUNCTION prevent_mutation();

-- SETTLEMENT STATE HISTORY: fully immutable audit trail
CREATE TRIGGER no_update_settlement_history
BEFORE UPDATE ON settlement_state_history
FOR EACH ROW EXECUTE FUNCTION prevent_mutation();

CREATE TRIGGER no_delete_settlement_history
BEFORE DELETE ON settlement_state_history
FOR EACH ROW EXECUTE FUNCTION prevent_mutation();

-- RECONCILIATION RESULTS: immutable audit records
CREATE TRIGGER no_update_reconciliation
BEFORE UPDATE ON reconciliation_results
FOR EACH ROW EXECUTE FUNCTION prevent_mutation();

CREATE TRIGGER no_delete_reconciliation
BEFORE DELETE ON reconciliation_results
FOR EACH ROW EXECUTE FUNCTION prevent_mutation();
