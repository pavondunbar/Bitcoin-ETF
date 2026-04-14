from events.events import EventType


ALLOWED_TRANSITIONS = {
    EventType.TRADE_CREATED: [EventType.BASKET_REQUESTED],
    EventType.BASKET_REQUESTED: [EventType.NETTING_EXECUTED],
    EventType.NETTING_EXECUTED: [EventType.SETTLEMENT_PENDING],
    EventType.SETTLEMENT_PENDING: [EventType.SETTLEMENT_FINALIZED],
    EventType.SETTLEMENT_FINALIZED: [EventType.CUSTODY_UPDATED],
}


def validate_transition(current: EventType, next_event: EventType):
    if next_event not in ALLOWED_TRANSITIONS.get(current, []):
        raise Exception(f"Invalid transition: {current} -> {next_event}")
