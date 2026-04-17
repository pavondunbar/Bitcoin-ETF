from services.blockchain import simulate_broadcast, simulate_confirmation
from services.mpc_signing import request_mpc_signature


def settle_onchain(settlement_id, amount, signature):
    """Full on-chain settlement: broadcast + confirm."""
    broadcast = simulate_broadcast(settlement_id, amount, signature)
    confirmation = simulate_confirmation(
        broadcast["tx_hash"],
        broadcast["block_number"],
    )
    return {
        "onchain": broadcast,
        "confirmation": confirmation,
        "final": True,
    }


def settle_fiat(amount):
    return {
        "fedwire_ref": f"FW-{abs(hash(str(amount))) % 10**8:08d}",
        "amount": amount,
        "currency": "USD",
        "status": "settled",
    }


def hybrid_settlement(settlement_id, amount, signature):
    chain = settle_onchain(settlement_id, amount, signature)
    fiat = settle_fiat(amount)

    return {
        "onchain": chain,
        "fiat": fiat,
        "final": True,
    }
