import json
from core.db import get_conn


def persist_event(event):
    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO event_log (id, event_type, payload, idempotency_key)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (idempotency_key) DO NOTHING
            """,
            (
                str(event.id),                 # ✅ use event's UUID
                str(event.type),
                json.dumps(event.payload),
                event.idempotency_key,         # ✅ critical for dedup
            ),
        )

        conn.commit()

        # 👇 KEY: detect duplicate
        if cur.rowcount == 0:
            return False  # duplicate event

        return True  # successfully inserted

    finally:
        cur.close()
        conn.close()
