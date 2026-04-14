def on_trade_created(event):
    return {"type": "BasketRequested", "data": event}

def on_basket_requested(event):
    return {"type": "NettingExecuted", "data": event}

def on_netting_executed(event):
    return {"type": "SettlementPending", "data": event}

def on_settlement_pending(event):
    return {"type": "SettlementFinalized", "data": event}

def on_settlement_finalized(event):
    return {"type": "CustodyUpdated", "data": event}
