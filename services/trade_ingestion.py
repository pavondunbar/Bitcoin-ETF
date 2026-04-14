from events.events import Event, EventType


def trade_ingestion_handler(bus):
    def handle(event: Event):
        print("[TRADE] Processing trade:", event.payload)

        bus.publish(Event(
            type=EventType.BASKET_REQUESTED,
            payload=event.payload
        ))

    return handle
