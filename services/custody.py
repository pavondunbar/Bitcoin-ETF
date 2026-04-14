from events.events import Event, EventType


def custody_handler(bus):
    def handle(event: Event):
        print("[CUSTODY] Updating ledger finality")

        bus.publish(Event(
            type=EventType.CUSTODY_UPDATED,
            payload=event.payload
        ))

    return handle
