import time
import json
from core.db import get_conn
from core.kafka_producer import publish_to_kafka


def poll_outbox():
    conn = get_conn()
    cur = conn.cursor()

    while True:
        cur.execute("""
            SELECT id, event_type, payload
            FROM outbox_events
            WHERE published_at IS NULL
            ORDER BY created_at
            LIMIT 100
        """)

        rows = cur.fetchall()

        for row in rows:
            event_id, event_type, payload = row

            # publish to kafka
            publish_to_kafka({
                "id": str(event_id),
                "type": event_type,
                "payload": payload
            })

            # mark as published
            cur.execute("""
                UPDATE outbox_events
                SET published_at = now()
                WHERE id = %s
            """, (event_id,))

        conn.commit()
        time.sleep(1)


if __name__ == "__main__":
    poll_outbox()
