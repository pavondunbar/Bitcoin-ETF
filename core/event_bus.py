import json
from typing import Callable, Dict, List
from datetime import datetime

from core.event_store import persist_event


class EventBus:
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)

    # ---------------------------------------------------------
    # SAFE SERIALIZATION (replay + logging safe)
    # ---------------------------------------------------------
    def _safe_json(self, obj):
        def default(o):
            if isinstance(o, set):
                return list(o)
            if isinstance(o, datetime):
                return o.isoformat()
            return str(o)

        return json.dumps(obj, indent=2, default=default)

    # ---------------------------------------------------------
    # CORE PUBLISH PIPELINE (IDEMPOTENT + OUTBOX SAFE)
    # ---------------------------------------------------------
    def publish(self, event):
        """
        OUTBOX-CORRECT FLOW:

        1. Persist event (event_log + outbox write happens inside event_store)
        2. If duplicate → STOP immediately
        3. Log event
        4. Dispatch to in-process subscribers ONLY

        NOTE:
        Kafka is NOT called here anymore
        Kafka is handled asynchronously by outbox worker
        """

        # -----------------------------------------------------
        # 1. PERSIST (IDEMPOTENCY GATE + OUTBOX WRITE)
        # -----------------------------------------------------
        inserted = persist_event(event)

        # -----------------------------------------------------
        # 2. DUPLICATE SHORT-CIRCUIT
        # -----------------------------------------------------
        if not inserted:
            print(
                f"[IDEMPOTENT-SKIP] {event.type} "
                f"({getattr(event, 'idempotency_key', None)})"
            )
            return

        # -----------------------------------------------------
        # 3. LOG EVENT (OBSERVABILITY ONLY)
        # -----------------------------------------------------
        print(f"[EVENT] {event.type} -> {self._safe_json(event.payload)}")

        # -----------------------------------------------------
        # 4. DISPATCH TO SUBSCRIBERS ONLY
        # -----------------------------------------------------
        handlers = self.subscribers.get(event.type, [])

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                print(f"[HANDLER ERROR] {event.type}: {e}")
