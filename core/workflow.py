def on_trade_created(event):
    return {"type": "BasketRequested", "data": event}

def on_basket_requested(event):
    return {"type": "NettingExecuted", "data": event}

def on_netting_executed(event):
    return {"type": "SettlementPending", "data": event}

def on_settlement_pending(event):
    return {"type": "SettlementApproved", "data": event}

def on_settlement_approved(event):
    return {"type": "SettlementSigned", "data": event}

def on_settlement_signed(event):
    return {"type": "SettlementBroadcasted", "data": event}

def on_settlement_broadcasted(event):
    return {"type": "SettlementConfirmed", "data": event}

def on_settlement_confirmed(event):
    return {"type": "CustodyUpdated", "data": event}

def on_custody_updated(event):
    return {"type": "Complete", "data": event}
