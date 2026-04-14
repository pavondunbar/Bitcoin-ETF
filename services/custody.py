from events.events import Event, EventType


def custody_handler(bus):
    def handle(event: Event):
        print("[CUSTODY] Updating ledger finality")

        # ----------------------------------------------------
        # STATE PROPAGATION FIX
        # ----------------------------------------------------
        new_payload = {
            **event.payload,
            "custody_updated": True,
            "finality_status": "CONFIRMED"
        }

        bus.publish(Event(
            type=EventType.CUSTODY_UPDATED,
            payload=new_payload
        ))

    return handle
