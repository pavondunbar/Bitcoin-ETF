from core.event_bus import EventBus
from core import workflow


def build_system():
    bus = EventBus()

    # -------------------------------------------------------
    # WIRE EVENT → HANDLER MAP
    # -------------------------------------------------------

    bus.subscribe("TradeCreated", workflow.on_trade_created)
    bus.subscribe("BasketRequested", workflow.on_basket_requested)
    bus.subscribe("NettingExecuted", workflow.on_netting_executed)
    bus.subscribe("SettlementPending", workflow.on_settlement_pending)
    bus.subscribe("SettlementFinalized", workflow.on_settlement_finalized)
    bus.subscribe("CustodyUpdated", workflow.on_custody_updated)

    return bus
