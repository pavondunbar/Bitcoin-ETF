from events.events import Event, EventType


def netting_handler(bus):
    def handle(event: Event):
        net_qty = event.payload["qty"] - 1  # simplified netting

        print(
            f"[NETTING] Executed net qty: {net_qty} "
            f"(trace={event.trace_id})"
        )

        new_payload = {
            **event.payload,
            "net_qty": net_qty,
        }

        bus.publish(event.child(
            EventType.NETTING_EXECUTED,
            new_payload,
        ))

    return handle
