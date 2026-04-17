import hashlib
import random
import time
from datetime import datetime, timezone


# ---------------------------------------------------------------
# SIMULATED BLOCKCHAIN RAILS
#
# Generates realistic-looking transaction hashes, block numbers,
# and confirmation counts for demo purposes.
#
# In production: replace with Web3.py / bitcoinlib RPC calls.
# ---------------------------------------------------------------

# Simulated chain state
_block_counter = 850_000  # approximate Bitcoin block height


def simulate_broadcast(
    settlement_id: str, amount: float, signature: str,
) -> dict:
    """
    Simulate broadcasting a signed transaction to the blockchain.

    Returns a realistic tx_hash (64-char hex) and block number.
    """
    global _block_counter
    _block_counter += 1

    # Deterministic tx_hash from settlement data
    tx_input = (
        f"{settlement_id}:{amount}:{signature}:"
        f"{datetime.now(timezone.utc).isoformat()}"
    )
    tx_hash = "0x" + hashlib.sha256(
        tx_input.encode("utf-8")
    ).hexdigest()

    return {
        "tx_hash": tx_hash,
        "block_number": _block_counter,
        "gas_used": random.randint(21_000, 65_000),
        "network": "bitcoin-mainnet-simulated",
        "broadcasted_at": datetime.now(timezone.utc).isoformat(),
    }


def simulate_confirmation(tx_hash: str, block_number: int) -> dict:
    """
    Simulate waiting for block confirmations.

    In production: poll RPC for confirmation depth.
    For demo: returns 6 confirmations (Bitcoin standard).
    """
    confirmations = 6  # Bitcoin finality threshold

    return {
        "tx_hash": tx_hash,
        "block_number": block_number,
        "confirmations": confirmations,
        "confirmation_block": block_number + confirmations,
        "finality": "confirmed",
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
    }
