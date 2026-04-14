from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


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
