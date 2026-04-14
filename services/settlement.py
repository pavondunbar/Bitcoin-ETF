from events.events import Event, EventType
from datetime import datetime, timezone


def settlement_handler(bus):
    def handle(event):
        print("[SETTLEMENT] Processing settlement...")

        # ----------------------------------------------------
        # STEP 1: SETTLEMENT PENDING
        # ----------------------------------------------------
        pending_payload = {
            **event.payload,
            "settlement_status": "PENDING",
            "settlement_initiated_at": datetime.now(timezone.utc).isoformat()
        }

        bus.publish(Event(
            type=EventType.SETTLEMENT_PENDING,
            payload=pending_payload
        ))

        # simulate confirmation (T+0 for demo)
        print("[SETTLEMENT] Finalized")

        # ----------------------------------------------------
        # STEP 2: SETTLEMENT FINALIZED
        # ----------------------------------------------------
        finalized_payload = {
            **pending_payload,
            "settlement_status": "FINALIZED",
            "settlement_finalized_at": datetime.now(timezone.utc).isoformat()
        }

        bus.publish(Event(
            type=EventType.SETTLEMENT_FINALIZED,
            payload=finalized_payload
        ))

    return handle
