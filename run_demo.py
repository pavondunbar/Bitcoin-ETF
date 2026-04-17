import random
import time
from datetime import datetime, timezone

from core.event_bus import EventBus
from core.replay import replay, rebuild_state
from events.events import Event, EventType

from services.trade_ingestion import trade_ingestion_handler
from services.netting import netting_handler
from services.settlement import settlement_handler
from services.custody import custody_handler
from services.ledger_posting import ledger_posting_handler
from services.reconciliation.main import run_reconciliation


# ------------------------------------------------------------
# LOGGING
# ------------------------------------------------------------
def log(step, msg):
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[{ts}] [{step}] {msg}")


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
    print("\n" + "=" * 60)
    print("  ETF SETTLEMENT LIFECYCLE SIMULATOR")
    print("  Blockchain Rails + MPC Signing + Audit Trails")
    print("=" * 60 + "\n")

    bus = EventBus()

    # --------------------------------------------------------
    # EVENT WIRING (full pipeline)
    # --------------------------------------------------------
    # Trade lifecycle
    bus.subscribe(EventType.TRADE_CREATED,
                  trade_ingestion_handler(bus))
    bus.subscribe(EventType.BASKET_REQUESTED,
                  netting_handler(bus))

    # Settlement state machine:
    # NETTING_EXECUTED → PENDING → APPROVED → SIGNED →
    # BROADCASTED → CONFIRMED
    bus.subscribe(EventType.NETTING_EXECUTED,
                  settlement_handler(bus))

    # Post-settlement custody
    bus.subscribe(EventType.SETTLEMENT_CONFIRMED,
                  custody_handler(bus))

    # Ledger posting (double-entry accounting)
    bus.subscribe(EventType.TRADE_CREATED,
                  ledger_posting_handler(bus))
    bus.subscribe(EventType.NETTING_EXECUTED,
                  ledger_posting_handler(bus))
    bus.subscribe(EventType.SETTLEMENT_CONFIRMED,
                  ledger_posting_handler(bus))

    # --------------------------------------------------------
    # OPTIONAL REPLAY MODE
    # --------------------------------------------------------
    ENABLE_REPLAY = False

    if ENABLE_REPLAY:
        print("[REPLAY] Replaying event log into system...")
        replay(bus)

    # --------------------------------------------------------
    # MARKET SIMULATION LOOP
    # --------------------------------------------------------
    CYCLES = 3  # number of trade cycles to run
    cycle = 0

    while cycle < CYCLES:
        cycle += 1
        print(f"\n{'─' * 60}")
        print(f"  TRADE CYCLE {cycle}/{CYCLES}")
        print(f"{'─' * 60}")

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
            actor="demo-ap",  # authorized participant
        )

        bus.publish(event)

        time.sleep(1)

    # --------------------------------------------------------
    # POST-DEMO: RECONCILIATION
    # --------------------------------------------------------
    print(f"\n{'─' * 60}")
    print("  RUNNING RECONCILIATION ENGINE")
    print(f"{'─' * 60}")

    recon_result = run_reconciliation()

    # --------------------------------------------------------
    # POST-DEMO: STATE REBUILD
    # --------------------------------------------------------
    print(f"\n{'─' * 60}")
    print("  RUNNING DETERMINISTIC STATE REBUILD")
    print(f"{'─' * 60}")

    state = rebuild_state()

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------
    print(f"\n{'=' * 60}")
    print("  DEMO COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Trades processed:   {CYCLES}")
    print(f"  Reconciliation:     {recon_result['status']}")
    print(
        f"  Ledger balanced:    "
        f"{state['invariants']['debit_credit_balanced']}"
    )
    print(
        f"  Journal entries:    "
        f"{state['invariants']['total_journal_entries']}"
    )
    print(f"  Settlement states:  {state['settlement_states']}")
    print(f"{'=' * 60}\n")


# ------------------------------------------------------------
# ENTRYPOINT
# ------------------------------------------------------------
if __name__ == "__main__":
    main()
