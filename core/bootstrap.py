from core.event_bus import EventBus
from events.events import EventType

from services.trade_ingestion import trade_ingestion_handler
from services.netting import netting_handler
from services.settlement import settlement_handler
from services.custody import custody_handler
from services.ledger_posting import ledger_posting_handler


def build_system():
    bus = EventBus()

    # -------------------------------------------------------
    # TRADE LIFECYCLE PIPELINE
    # -------------------------------------------------------
    bus.subscribe(EventType.TRADE_CREATED,
                  trade_ingestion_handler(bus))
    bus.subscribe(EventType.BASKET_REQUESTED,
                  netting_handler(bus))

    # -------------------------------------------------------
    # SETTLEMENT STATE MACHINE
    # NETTING_EXECUTED triggers the full settlement pipeline:
    # PENDING → APPROVED → SIGNED → BROADCASTED → CONFIRMED
    # -------------------------------------------------------
    bus.subscribe(EventType.NETTING_EXECUTED,
                  settlement_handler(bus))

    # -------------------------------------------------------
    # POST-SETTLEMENT CUSTODY UPDATE
    # -------------------------------------------------------
    bus.subscribe(EventType.SETTLEMENT_CONFIRMED,
                  custody_handler(bus))

    # -------------------------------------------------------
    # LEDGER POSTING (double-entry journal for accounting events)
    # -------------------------------------------------------
    bus.subscribe(EventType.TRADE_CREATED,
                  ledger_posting_handler(bus))
    bus.subscribe(EventType.NETTING_EXECUTED,
                  ledger_posting_handler(bus))
    bus.subscribe(EventType.SETTLEMENT_CONFIRMED,
                  ledger_posting_handler(bus))

    return bus
