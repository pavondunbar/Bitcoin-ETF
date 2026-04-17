from events.events import Event, EventType
from datetime import datetime, timezone


def trade_ingestion_handler(bus):
    def handle(event: Event):
        print(
            f"[TRADE] Processing trade "
            f"(trace={event.trace_id}, actor={event.actor})"
        )

        new_payload = {
            **event.payload,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "status": "INGESTED",
        }

        bus.publish(event.child(
            EventType.BASKET_REQUESTED,
            new_payload,
        ))

    return handle
