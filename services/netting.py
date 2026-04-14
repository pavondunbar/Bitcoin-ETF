from events.events import Event, EventType


def netting_handler(bus):
    def handle(event: Event):
        net_qty = event.payload["qty"] - 1  # simplified netting logic

        print("[NETTING] Executed net qty:", net_qty)

        bus.publish(Event(
            type=EventType.SETTLEMENT_PENDING,
            payload={**event.payload, "net_qty": net_qty}
        ))

    return handle
