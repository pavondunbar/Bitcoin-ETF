import hashlib
import json
import random


# ---------------------------------------------------------------
# MPC NODE SIMULATION (2-of-3 QUORUM)
#
# In production this calls out to isolated MPC nodes over gRPC.
# For demo: deterministic partial signatures using HMAC-SHA256
# with per-node keys.
# ---------------------------------------------------------------

NODE_KEYS = {
    "node-1": "mpc_key_alpha_7f3a",
    "node-2": "mpc_key_bravo_9c1d",
    "node-3": "mpc_key_charlie_2e8b",
}

QUORUM_REQUIRED = 2
TOTAL_NODES = 3


def _partial_sign(node_id: str, payload: str) -> str:
    """Simulate a partial signature from one MPC node."""
    key = NODE_KEYS[node_id]
    raw = f"{key}:{payload}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def request_mpc_signature(payload: str) -> dict:
    """
    Request 2-of-3 MPC threshold signature.

    Selects 2 random nodes from the 3-node cluster,
    collects partial signatures, and combines them
    into a single composite signature.
    """
    all_nodes = list(NODE_KEYS.keys())

    # Select quorum (2 of 3)
    signing_nodes = sorted(random.sample(all_nodes, QUORUM_REQUIRED))

    # Collect partial signatures
    partials = {}
    for node_id in signing_nodes:
        partials[node_id] = _partial_sign(node_id, payload)

    # Combine: hash of sorted partial signatures
    combined_input = "|".join(
        f"{nid}={sig}" for nid, sig in sorted(partials.items())
    )
    combined_signature = hashlib.sha256(
        combined_input.encode("utf-8")
    ).hexdigest()

    return {
        "combined_signature": combined_signature,
        "signing_nodes": signing_nodes,
        "quorum": f"{QUORUM_REQUIRED}-of-{TOTAL_NODES}",
        "quorum_json": json.dumps({
            "nodes": signing_nodes,
            "partials": partials,
            "threshold": QUORUM_REQUIRED,
            "total": TOTAL_NODES,
        }),
        "payload_hash": payload,
    }
