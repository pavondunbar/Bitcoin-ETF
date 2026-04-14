from events.events import Event, EventType
from datetime import datetime, timezone


def trade_ingestion_handler(bus):
    def handle(event: Event):
        print("[TRADE] Processing trade:", event.payload)

        # ----------------------------------------------------
        # STATE PROPAGATION FIX (enrich trade context)
        # ----------------------------------------------------
        new_payload = {
            **event.payload,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "status": "INGESTED"
        }

        bus.publish(Event(
            type=EventType.BASKET_REQUESTED,
            payload=new_payload
        ))

    return handle
