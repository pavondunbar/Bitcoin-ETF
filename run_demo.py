import random
import time
from datetime import datetime, timezone

from core.event_bus import EventBus
from services.trade_ingestion import trade_ingestion_handler
from services.netting import netting_handler
from services.settlement import settlement_handler
from services.custody import custody_handler


# ------------------------------------------------------------
# LOGGING (FIXED: NO utcnow DEPRECATION)
# ------------------------------------------------------------
def log(step, msg):
    print(f"[{datetime.now(timezone.utc).isoformat()}] [{step}] {msg}")


# ------------------------------------------------------------
# MARKET DATA (SIMULATED OR ORACLE)
# ------------------------------------------------------------
def get_price():
    return 65000 + random.randint(-500, 500)


# ------------------------------------------------------------
# BASKET GENERATION (AP LOGIC)
# ------------------------------------------------------------
def create_basket(price):
    shares = random.randint(1000, 5000)
    nav = price * shares

    basket = {
        "symbol": "BTC-ETF",
        "shares": shares,
        "nav": nav,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    log("AP", f"Creating basket: shares={shares}, nav={nav}")
    return basket


# ------------------------------------------------------------
# MAIN EVENT-DRIVEN PIPELINE
# ------------------------------------------------------------
def main():
    print("\n=== ETF EVENT-DRIVEN SIMULATION ENGINE STARTED ===\n")

    bus = EventBus()

    # --------------------------------------------------------
    # EVENT WIRING (IMPORTANT FIX: NO CURRIED HANDLERS)
    # --------------------------------------------------------
    bus.subscribe("TradeCreated", trade_ingestion_handler(bus))
    bus.subscribe("BasketRequested", netting_handler(bus))
    bus.subscribe("NettingExecuted", settlement_handler(bus))
    bus.subscribe("SettlementFinalized", custody_handler(bus))

    # --------------------------------------------------------
    # SEED LOOP (ONLY MARKET INPUT — NOT BUSINESS LOGIC)
    # --------------------------------------------------------
    while True:
        price = get_price()
        log("MARKET", f"BTC price={price}")

        basket = create_basket(price)

        # ----------------------------------------------------
        # FIXED EVENT PUBLISHING (STRING-BASED EVENT MODEL)
        # ----------------------------------------------------
        bus.publish(
            "TradeCreated",
            {
                "qty": basket["shares"],
                "nav": basket["nav"],
                "symbol": basket["symbol"],
                "timestamp": basket["timestamp"],
            },
        )

        time.sleep(5)


# ------------------------------------------------------------
# ENTRYPOINT
# ------------------------------------------------------------
if __name__ == "__main__":
    main()
