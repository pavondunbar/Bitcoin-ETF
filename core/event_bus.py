import json
from typing import Callable, Dict, List
from datetime import datetime
from core.event_store import persist_event  # 👈 NEW (event_log writer)


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
    # CORE PUBLISH PIPELINE
    # ---------------------------------------------------------
    def publish(self, event):
        """
        Event flow:
        1. Persist event (event sourcing)
        2. Log event
        3. Dispatch to subscribers
        """

        # -----------------------------------------------------
        # 1. PERSIST EVENT (EVENT STORE)
        # -----------------------------------------------------
        persist_event(event)   # 👈 THIS is the key upgrade

        # -----------------------------------------------------
        # 2. LOG EVENT (DEBUG / OBSERVABILITY)
        # -----------------------------------------------------
        print(f"[EVENT] {event.type} -> {self._safe_json(event.payload)}")

        # -----------------------------------------------------
        # 3. DISPATCH TO HANDLERS
        # -----------------------------------------------------
        handlers = self.subscribers.get(event.type, [])

        for handler in handlers:
            handler(event)
