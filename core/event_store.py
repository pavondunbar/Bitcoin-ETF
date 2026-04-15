import json
import uuid
from core.db import get_conn


def persist_event(event):
    """
    OUTBOX PATTERN IMPLEMENTATION

    Flow:
    1. Insert into event_log (source of truth)
    2. Insert into outbox (delivery queue to Kafka)
    3. Enforce idempotency via UNIQUE(idempotency_key)
    """

    conn = get_conn()
    cur = conn.cursor()

    try:
        event_id = str(getattr(event, "id", uuid.uuid4()))
        idempotency_key = getattr(event, "idempotency_key", None)

        if idempotency_key is None:
            raise ValueError("Event missing idempotency_key (required for deduplication)")

        payload_json = json.dumps(event.payload)

        # =========================================================
        # 1. INSERT INTO EVENT LOG (SOURCE OF TRUTH)
        # =========================================================
        cur.execute(
            """
            INSERT INTO event_log (id, event_type, payload, idempotency_key)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (idempotency_key) DO NOTHING
            """,
            (
                event_id,
                str(event.type),
                payload_json,
                idempotency_key,
            ),
        )

        # If duplicate → short-circuit BEFORE outbox write
        if cur.rowcount == 0:
            conn.commit()
            return False

        # =========================================================
        # 2. INSERT INTO OUTBOX (KAFKA DELIVERY QUEUE)
        # =========================================================
        cur.execute(
            """
            INSERT INTO outbox (id, event_id, event_type, payload, status)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                str(uuid.uuid4()),
                event_id,
                str(event.type),
                payload_json,
                "PENDING",
            ),
        )

        # =========================================================
        # 3. COMMIT ATOMICALLY
        # =========================================================
        conn.commit()

        return True

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        cur.close()
        conn.close()
