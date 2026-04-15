from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict
import uuid


class EventType(str, Enum):
    TRADE_CREATED = "TradeCreated"
    BASKET_REQUESTED = "BasketRequested"
    NETTING_EXECUTED = "NettingExecuted"
    SETTLEMENT_PENDING = "SettlementPending"
    SETTLEMENT_FINALIZED = "SettlementFinalized"
    CUSTODY_UPDATED = "CustodyUpdated"


@dataclass
class Event:
    type: EventType
    payload: Dict[str, Any]

    # unique event identifier
    id: uuid.UUID = field(default_factory=uuid.uuid4)

    # idempotency key (used for deduplication)
    idempotency_key: str = field(default=None)

    def __post_init__(self):
        # if no idempotency key provided, default to event id
        if self.idempotency_key is None:
            self.idempotency_key = str(self.id)
