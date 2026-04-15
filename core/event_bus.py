import json
from typing import Callable, Dict, List
from datetime import datetime

from core.event_store import persist_event
from core.kafka_producer import publish_to_kafka  # 👈 add kafka mirror


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
    # CORE PUBLISH PIPELINE (IDEMPOTENT)
    # ---------------------------------------------------------
    def publish(self, event):
        """
        Flow:
        1. Persist event (event_log) with idempotency guard
        2. If duplicate → STOP (no downstream effects)
        3. Mirror to Kafka
        4. Log event
        5. Dispatch to handlers
        """

        # 1. PERSIST (IDEMPOTENCY GATE)
        inserted = persist_event(event)

        # 2. DUPLICATE SHORT-CIRCUIT
        if not inserted:
            print(f"[IDEMPOTENT-SKIP] {event.type} ({getattr(event, 'idempotency_key', None)})")
            return

        # 3. KAFKA MIRROR (ONLY ONCE)
        publish_to_kafka(event)

        # 4. LOG EVENT
        print(f"[EVENT] {event.type} -> {self._safe_json(event.payload)}")

        # 5. DISPATCH TO SUBSCRIBERS
        handlers = self.subscribers.get(event.type, [])
        for handler in handlers:
            handler(event)
