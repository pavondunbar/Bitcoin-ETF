from events.events import Event, EventType


def netting_handler(bus):
    def handle(event: Event):
        # ----------------------------------------------------
        # NETTING CALCULATION
        # ----------------------------------------------------
        net_qty = event.payload["qty"] - 1  # simplified netting logic

        print("[NETTING] Executed net qty:", net_qty)

        # ----------------------------------------------------
        # STATE PROPAGATION FIX
        # ----------------------------------------------------
        new_payload = {
            **event.payload,
            "net_qty": net_qty
        }

        bus.publish(Event(
            type=EventType.NETTING_EXECUTED,
            payload=new_payload
        ))

    return handle
