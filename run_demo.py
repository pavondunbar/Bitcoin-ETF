import random
import time
from datetime import datetime, timezone

from core.event_bus import EventBus
from core.replay import replay
from events.events import Event, EventType
from services.trade_ingestion import trade_ingestion_handler
from services.netting import netting_handler
from services.settlement import settlement_handler
from services.custody import custody_handler


# ------------------------------------------------------------
# LOGGING
# ------------------------------------------------------------
def log(step, msg):
    print(f"[{datetime.now(timezone.utc).isoformat()}] [{step}] {msg}")


# ------------------------------------------------------------
# MARKET DATA
# ------------------------------------------------------------
def get_price():
    return 65000 + random.randint(-500, 500)


# ------------------------------------------------------------
# BASKET GENERATION
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
# MAIN
# ------------------------------------------------------------
def main():
    print("\n=== ETF EVENT-DRIVEN SIMULATION ENGINE STARTED ===\n")

    bus = EventBus()

    # --------------------------------------------------------
    # EVENT WIRING
    # --------------------------------------------------------
    bus.subscribe(EventType.TRADE_CREATED, trade_ingestion_handler(bus))
    bus.subscribe(EventType.BASKET_REQUESTED, netting_handler(bus))
    bus.subscribe(EventType.NETTING_EXECUTED, settlement_handler(bus))
    bus.subscribe(EventType.SETTLEMENT_FINALIZED, custody_handler(bus))

    # --------------------------------------------------------
    # OPTIONAL REPLAY MODE
    # --------------------------------------------------------
    ENABLE_REPLAY = False

    if ENABLE_REPLAY:
        print("[REPLAY] Replaying event log into system...")
        replay(bus)

    # --------------------------------------------------------
    # SEED LOOP (market events only)
    # --------------------------------------------------------
    while True:
        price = get_price()
        log("MARKET", f"BTC price={price}")

        basket = create_basket(price)

        event = Event(
            type=EventType.TRADE_CREATED,
            payload={
                "qty": basket["shares"],
                "nav": basket["nav"],
                "symbol": basket["symbol"],
                "timestamp": basket["timestamp"],
            },
        )

        bus.publish(event)

        time.sleep(5)


# ------------------------------------------------------------
# ENTRYPOINT
# ------------------------------------------------------------
if __name__ == "__main__":
    main()
