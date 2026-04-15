import time
import json
from core.db import get_conn
from core.kafka_producer import publish_to_kafka


POLL_INTERVAL_SECONDS = 1


def fetch_unprocessed(limit=100):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, event_type, payload, idempotency_key
        FROM event_log
        WHERE processed = FALSE
        ORDER BY created_at ASC
        LIMIT %s
        FOR UPDATE SKIP LOCKED
        """,
        (limit,),
    )

    rows = cur.fetchall()
    conn.close()
    return rows


def mark_processed(event_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE event_log
        SET processed = TRUE,
            processed_at = NOW()
        WHERE id = %s
        """,
        (event_id,),
    )

    conn.commit()
    conn.close()


def run_outbox_worker():
    print("[OUTBOX] Worker started...")

    while True:
        events = fetch_unprocessed()

        if not events:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        for event_id, event_type, payload, idem_key in events:
            try:
                event = {
                    "id": str(event_id),
                    "type": event_type,
                    "payload": payload,
                    "idempotency_key": idem_key,
                }

                # RELAY TO KAFKA
                publish_to_kafka(event)

                # MARK AS SENT
                mark_processed(event_id)

                print(f"[OUTBOX] published {event_type} {event_id}")

            except Exception as e:
                print(f"[OUTBOX-ERROR] {event_id} -> {e}")

        time.sleep(POLL_INTERVAL_SECONDS)
