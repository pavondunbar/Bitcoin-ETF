from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional
import uuid


class EventType(str, Enum):
    # TRADE LIFECYCLE
    TRADE_CREATED = "TradeCreated"
    BASKET_REQUESTED = "BasketRequested"
    NETTING_EXECUTED = "NettingExecuted"

    # SETTLEMENT STATE MACHINE
    # PENDING → APPROVED → SIGNED → BROADCASTED → CONFIRMED
    SETTLEMENT_PENDING = "SettlementPending"
    SETTLEMENT_APPROVED = "SettlementApproved"
    SETTLEMENT_SIGNED = "SettlementSigned"
    SETTLEMENT_BROADCASTED = "SettlementBroadcasted"
    SETTLEMENT_CONFIRMED = "SettlementConfirmed"

    # POST-SETTLEMENT
    CUSTODY_UPDATED = "CustodyUpdated"


@dataclass
class Event:
    type: EventType
    payload: Dict[str, Any]

    # unique event identifier
    id: uuid.UUID = field(default_factory=uuid.uuid4)

    # idempotency key (used for deduplication)
    idempotency_key: str = field(default=None)

    # AUDIT CONTEXT: traces every state transition back to origin
    request_id: Optional[str] = field(default=None)
    trace_id: Optional[str] = field(default=None)
    actor: Optional[str] = field(default=None)

    def __post_init__(self):
        # if no idempotency key provided, default to event id
        if self.idempotency_key is None:
            self.idempotency_key = str(self.id)
        # if no trace_id, generate one (root trace)
        if self.trace_id is None:
            self.trace_id = str(uuid.uuid4())
        # if no request_id, generate one
        if self.request_id is None:
            self.request_id = str(uuid.uuid4())

    def child(
        self,
        event_type: EventType,
        payload: Dict[str, Any],
        actor: Optional[str] = None,
    ) -> "Event":
        """Create a child event that inherits trace context."""
        return Event(
            type=event_type,
            payload=payload,
            trace_id=self.trace_id,
            request_id=self.request_id,
            actor=actor or self.actor,
        )
