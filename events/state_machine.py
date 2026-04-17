from events.events import EventType


# ---------------------------------------------------------------
# TRADE LIFECYCLE TRANSITIONS
# ---------------------------------------------------------------
TRADE_TRANSITIONS = {
    EventType.TRADE_CREATED: [EventType.BASKET_REQUESTED],
    EventType.BASKET_REQUESTED: [EventType.NETTING_EXECUTED],
    EventType.NETTING_EXECUTED: [EventType.SETTLEMENT_PENDING],
}

# ---------------------------------------------------------------
# SETTLEMENT STATE MACHINE (DETERMINISTIC)
# PENDING → APPROVED → SIGNED → BROADCASTED → CONFIRMED
# ---------------------------------------------------------------
SETTLEMENT_TRANSITIONS = {
    EventType.SETTLEMENT_PENDING: [EventType.SETTLEMENT_APPROVED],
    EventType.SETTLEMENT_APPROVED: [EventType.SETTLEMENT_SIGNED],
    EventType.SETTLEMENT_SIGNED: [EventType.SETTLEMENT_BROADCASTED],
    EventType.SETTLEMENT_BROADCASTED: [EventType.SETTLEMENT_CONFIRMED],
    EventType.SETTLEMENT_CONFIRMED: [EventType.CUSTODY_UPDATED],
}

# ---------------------------------------------------------------
# COMBINED TRANSITIONS (full lifecycle)
# ---------------------------------------------------------------
ALLOWED_TRANSITIONS = {**TRADE_TRANSITIONS, **SETTLEMENT_TRANSITIONS}

# Settlement status string constants (for DB column)
SETTLEMENT_STATES = [
    "PENDING",
    "APPROVED",
    "SIGNED",
    "BROADCASTED",
    "CONFIRMED",
]

SETTLEMENT_STATE_ORDER = {
    state: idx for idx, state in enumerate(SETTLEMENT_STATES)
}


def validate_transition(current: EventType, next_event: EventType):
    allowed = ALLOWED_TRANSITIONS.get(current, [])
    if next_event not in allowed:
        raise ValueError(
            f"Invalid transition: {current} -> {next_event}. "
            f"Allowed: {allowed}"
        )


def validate_settlement_state(current_status: str, next_status: str):
    """Validate settlement status string transitions."""
    current_idx = SETTLEMENT_STATE_ORDER.get(current_status)
    next_idx = SETTLEMENT_STATE_ORDER.get(next_status)

    if current_idx is None:
        raise ValueError(f"Unknown settlement status: {current_status}")
    if next_idx is None:
        raise ValueError(f"Unknown settlement status: {next_status}")
    if next_idx != current_idx + 1:
        raise ValueError(
            f"Invalid settlement transition: {current_status} -> "
            f"{next_status}. Must advance exactly one step."
        )
