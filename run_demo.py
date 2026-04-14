import time
import random
import requests
from datetime import datetime

BASE_URLS = {
    "price_oracle": "http://localhost:8005",
    "trade_ingestion": "http://localhost:8001",
    "netting_engine": "http://localhost:8002",
    "settlement_engine": "http://localhost:8003",
    "custody": "http://localhost:8004",
    "reconciliation": "http://localhost:8006",
    "api_gateway": "http://localhost:8000",
}

def log(step, msg):
    print(f"[{datetime.utcnow().isoformat()}] [{step}] {msg}")

# ----------------------------
# 1. MARKET DATA → NAV INPUT
# ----------------------------
def get_price():
    # fallback simulated price if oracle endpoint isn't implemented
    try:
        r = requests.get(f"{BASE_URLS['price_oracle']}/price", timeout=2)
        return r.json()["price"]
    except:
        return 65000 + random.randint(-500, 500)

# ----------------------------
# 2. CREATE ETF BASKET
# ----------------------------
def create_etf_basket(price):
    shares = random.randint(1000, 5000)
    nav = price * shares

    payload = {
        "symbol": "BTC-ETF",
        "shares": shares,
        "nav": nav,
        "timestamp": datetime.utcnow().isoformat()
    }

    log("AP", f"Creating basket: shares={shares}, nav={nav}")

    try:
        requests.post(f"{BASE_URLS['api_gateway']}/create", json=payload, timeout=3)
    except:
        pass

    return payload

# ----------------------------
# 3. TRADE INGESTION
# ----------------------------
def ingest_trade(basket):
    trade = {
        "asset": "BTC",
        "qty": basket["shares"],
        "notional": basket["nav"]
    }

    log("TRADE", f"Ingesting trade qty={trade['qty']}")

    try:
        requests.post(f"{BASE_URLS['trade_ingestion']}/trade", json=trade, timeout=3)
    except:
        pass

    return trade

# ----------------------------
# 4. NETTING
# ----------------------------
def net(trade):
    netted = {
        "net_qty": trade["qty"] - random.randint(0, 10)
    }

    log("NETTING", f"Netted qty={netted['net_qty']}")

    return netted

# ----------------------------
# 5. SETTLEMENT
# ----------------------------
def settle(netted):
    settlement = {
        "status": "SETTLED" if netted["net_qty"] > 0 else "FAILED"
    }

    log("SETTLEMENT", f"Status={settlement['status']}")

    try:
        requests.post(f"{BASE_URLS['settlement_engine']}/settle", json=settlement, timeout=3)
    except:
        pass

    return settlement

# ----------------------------
# 6. CUSTODY UPDATE
# ----------------------------
def custody_update(settlement):
    log("CUSTODY", "Updating ledger")

    try:
        requests.post(f"{BASE_URLS['custody']}/update", json=settlement, timeout=3)
    except:
        pass

# ----------------------------
# 7. RECONCILIATION
# ----------------------------
def reconcile():
    log("RECON", "Running reconciliation check")

    try:
        requests.get(f"{BASE_URLS['reconciliation']}/run", timeout=3)
    except:
        pass

# ----------------------------
# MAIN LOOP
# ----------------------------
def run_cycle():
    price = get_price()
    log("MARKET", f"BTC price={price}")

    basket = create_etf_basket(price)
    trade = ingest_trade(basket)
    netted = net(trade)
    settlement = settle(netted)
    custody_update(settlement)
    reconcile()

if __name__ == "__main__":
    print("\n=== ETF SIMULATION ENGINE STARTED ===\n")

    while True:
        run_cycle()
        time.sleep(5)
