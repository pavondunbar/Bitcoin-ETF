from core.db import get_conn
from events.events import Event, EventType

def replay(bus):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT event_type, payload
        FROM event_log
        ORDER BY created_at ASC
    """)

    for event_type, payload in cur.fetchall():
        event = Event(
            type=EventType(event_type),
            payload=payload
        )
        bus.publish(event)
