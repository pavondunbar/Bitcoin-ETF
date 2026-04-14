import uuid
import json
from core.db import get_conn

def persist_event(event):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO event_log (id, event_type, payload)
        VALUES (%s, %s, %s)
        """,
        (
            str(uuid.uuid4()),
            str(event.type),
            json.dumps(event.payload)
        )
    )

    conn.commit()
