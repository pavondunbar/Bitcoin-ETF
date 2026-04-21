from fastapi import FastAPI, HTTPException
from services.blockchain import simulate_broadcast, simulate_confirmation
from services.mpc_signing import request_mpc_signature

app = FastAPI(title="Settlement Engine")


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


@app.post("/settle")
def settle(data: dict):
    settlement_id = data.get("settlement_id")
    amount = data.get("amount")
    signature = data.get("signature")
    if not settlement_id or amount is None:
        raise HTTPException(400, "Missing settlement_id or amount")
    return hybrid_settlement(settlement_id, amount, signature)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
