import hashlib
import json
from fastapi import FastAPI, HTTPException

app = FastAPI(title="MPC Signing Gateway")

QUORUM_REQUIRED = 2
TOTAL_NODES = 3


def combine_signatures(partials: dict) -> str:
    """
    Combine partial signatures from MPC nodes.
    Requires 2-of-3 quorum.
    """
    if len(partials) < QUORUM_REQUIRED:
        raise ValueError(
            f"Need {QUORUM_REQUIRED}-of-{TOTAL_NODES} quorum, "
            f"got {len(partials)}"
        )

    combined_input = "|".join(
        f"{nid}={sig}" for nid, sig in sorted(partials.items())
    )
    return hashlib.sha256(combined_input.encode("utf-8")).hexdigest()


@app.post("/sign")
def sign_transaction(data: dict):
    payload = data.get("payload")
    if not payload:
        raise HTTPException(400, "Missing payload to sign")

    partials = data.get("partials", {})
    if len(partials) < QUORUM_REQUIRED:
        raise HTTPException(
            400,
            f"Insufficient quorum: need {QUORUM_REQUIRED}, "
            f"got {len(partials)}",
        )

    combined = combine_signatures(partials)

    return {
        "combined_signature": combined,
        "quorum": f"{QUORUM_REQUIRED}-of-{TOTAL_NODES}",
        "signing_nodes": sorted(partials.keys()),
    }


@app.get("/health")
def health():
    return {"status": "ok", "quorum": f"{QUORUM_REQUIRED}/{TOTAL_NODES}"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
