import time
import json
from core.db import get_conn
from core.kafka_producer import publish_to_kafka, publish_to_dlq


POLL_INTERVAL_SECONDS = 1
MAX_RETRIES = 5
BACKOFF_BASE_SECONDS = 2


def fetch_pending(limit=100):
    """Fetch PENDING outbox events with row-level locking."""
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, event_id, event_type, payload, retry_count
        FROM outbox
        WHERE status = 'PENDING'
        ORDER BY created_at ASC
        LIMIT %s
        FOR UPDATE SKIP LOCKED
        """,
        (limit,),
    )

    rows = cur.fetchall()
    return conn, rows


def mark_sent(conn, outbox_id):
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE outbox
        SET status = 'SENT', sent_at = NOW()
        WHERE id = %s
        """,
        (outbox_id,),
    )


def mark_failed(conn, outbox_id, error_msg):
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE outbox
        SET retry_count = retry_count + 1,
            last_error = %s
        WHERE id = %s
        """,
        (error_msg, outbox_id),
    )


def mark_dlq(conn, outbox_id, error_msg):
    """Move to DLQ after max retries exhausted."""
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE outbox
        SET status = 'DLQ',
            last_error = %s
        WHERE id = %s
        """,
        (error_msg, outbox_id),
    )


def run_outbox_worker():
    print("[OUTBOX] Worker started (DLQ-enabled)...")

    while True:
        try:
            conn, events = fetch_pending()
        except Exception as e:
            print(f"[OUTBOX-ERROR] fetch failed: {e}")
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        if not events:
            conn.close()
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        for row in events:
            outbox_id = row["id"]
            event_type = row["event_type"]
            payload = row["payload"]
            retry_count = row["retry_count"]

            try:
                event_msg = {
                    "id": str(row["event_id"]),
                    "type": event_type,
                    "payload": payload,
                }

                publish_to_kafka(event_msg)
                mark_sent(conn, outbox_id)

                print(
                    f"[OUTBOX] published {event_type} "
                    f"(id={outbox_id})"
                )

            except Exception as e:
                error_msg = str(e)

                if retry_count >= MAX_RETRIES:
                    # EXHAUSTED RETRIES -> DEAD LETTER QUEUE
                    print(
                        f"[OUTBOX-DLQ] {event_type} "
                        f"(id={outbox_id}) -> DLQ after "
                        f"{retry_count} retries: {error_msg}"
                    )
                    mark_dlq(conn, outbox_id, error_msg)

                    # Publish to DLQ topic for manual review
                    try:
                        publish_to_dlq({
                            "outbox_id": str(outbox_id),
                            "event_type": event_type,
                            "payload": payload,
                            "retry_count": retry_count,
                            "last_error": error_msg,
                        })
                    except Exception as dlq_err:
                        print(
                            f"[OUTBOX-DLQ-ERROR] "
                            f"Failed to publish DLQ: {dlq_err}"
                        )
                else:
                    # RETRY WITH BACKOFF
                    backoff = BACKOFF_BASE_SECONDS ** retry_count
                    print(
                        f"[OUTBOX-RETRY] {event_type} "
                        f"(id={outbox_id}) retry "
                        f"{retry_count + 1}/{MAX_RETRIES}, "
                        f"backoff={backoff}s: {error_msg}"
                    )
                    mark_failed(conn, outbox_id, error_msg)

        conn.commit()
        conn.close()
        time.sleep(POLL_INTERVAL_SECONDS)
