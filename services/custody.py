from events.events import Event, EventType


def custody_handler(bus):
    def handle(event: Event):
        print(
            f"[CUSTODY] Updating ledger finality "
            f"(trace={event.trace_id})"
        )

        new_payload = {
            **event.payload,
            "custody_updated": True,
            "finality_status": "CONFIRMED",
        }

        bus.publish(event.child(
            EventType.CUSTODY_UPDATED,
            new_payload,
        ))

    return handle
