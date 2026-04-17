import hashlib
import os
from fastapi import FastAPI, HTTPException

app = FastAPI(title="MPC Signing Node")

NODE_ID = os.getenv("NODE_ID", "1")
NODE_KEY = os.getenv(
    "NODE_KEY",
    f"mpc_node_{NODE_ID}_secret_key",
)


def sign(payload: str) -> str:
    """Generate partial signature using this node's key material."""
    raw = f"{NODE_KEY}:{payload}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@app.post("/partial-sign")
def partial_sign(data: dict):
    payload = data.get("payload")
    if not payload:
        raise HTTPException(400, "Missing payload")

    partial = sign(payload)

    return {
        "node_id": f"node-{NODE_ID}",
        "partial_signature": partial,
        "payload_hash": hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest(),
    }


@app.get("/health")
def health():
    return {"status": "ok", "node_id": f"node-{NODE_ID}"}
