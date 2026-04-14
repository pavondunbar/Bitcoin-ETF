def settle_onchain(tx):
    return {
        "tx_hash": "0xabc123",
        "block_number": 123456
    }

def settle_fiat(amount):
    return {
        "fedwire_ref": "FW123456"
    }

def hybrid_settlement(tx, amount):
    chain = settle_onchain(tx)
    fiat = settle_fiat(amount)

    return {
        "onchain": chain,
        "fiat": fiat,
        "final": True
    }
