from events.events import Event, EventType


def settlement_handler(bus):
    def handle(event: Event):
        print("[SETTLEMENT] Finalizing batch")

        bus.publish(Event(
            type=EventType.SETTLEMENT_FINALIZED,
            payload=event.payload
        ))

    return handle
