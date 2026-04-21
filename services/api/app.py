import hashlib
import json
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Request, HTTPException
from kafka import KafkaProducer

from core.db import get_conn

app = FastAPI(title="ETF API Gateway")

producer = KafkaProducer(
    bootstrap_servers="kafka:9092",
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
)


# ---------------------------------------------------------------
# RBAC: ROLE-PERMISSION ENFORCEMENT
# ---------------------------------------------------------------

# Resource → action mapping per endpoint
ENDPOINT_PERMISSIONS = {
    ("POST", "/v1/etf/creation"): ("trade", "create"),
    ("POST", "/v1/etf/redemption"): ("trade", "create"),
    ("GET", "/v1/etf/nav-per-share"): ("trade", "read"),
    ("GET", "/v1/etf/holdings"): ("ledger", "read"),
    ("GET", "/v1/etf/fund-state"): ("ledger", "read"),
    ("POST", "/v1/settlement/approve"): ("settlement", "approve"),
    ("POST", "/v1/settlement/sign"): ("settlement", "sign"),
    ("GET", "/v1/settlement/status"): ("settlement", "read"),
    ("GET", "/v1/ledger/balances"): ("ledger", "read"),
    ("GET", "/v1/ledger/entries"): ("ledger", "read"),
    ("GET", "/health"): (None, None),  # public
}


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def authenticate(api_key: str):
    """Resolve API key to role. Returns (name, role) or raises."""
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing X-API-Key header",
        )

    key_hash = hash_api_key(api_key)
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT name, role FROM api_keys
        WHERE key_hash = %s AND is_active = TRUE
        """,
        (key_hash,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        raise HTTPException(
            status_code=401,
            detail="Invalid or inactive API key",
        )

    return row["name"], row["role"]


def authorize(role: str, resource: str, action: str):
    """Check if role has permission for resource+action."""
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT 1 FROM role_permissions
        WHERE role = %s
          AND (resource = %s OR resource = '*')
          AND (action = %s OR action = '*')
        LIMIT 1
        """,
        (role, resource, action),
    )
    allowed = cur.fetchone() is not None
    cur.close()
    conn.close()

    if not allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Role '{role}' lacks permission: "
                   f"{action} on {resource}",
        )


def audit_log(request_id, actor, role, method, path, status_code):
    """Publish audit trail entry to Kafka."""
    producer.send(
        "audit-trail",
        value={
            "request_id": request_id,
            "actor": actor,
            "role": role,
            "method": method,
            "path": path,
            "status_code": status_code,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


# ---------------------------------------------------------------
# MIDDLEWARE: auth + audit on every request
# ---------------------------------------------------------------

@app.middleware("http")
async def rbac_middleware(request: Request, call_next):
    request_id = request.headers.get(
        "X-Request-ID", str(uuid.uuid4())
    )
    path = request.url.path
    method = request.method

    # Health endpoint is public
    if path == "/health":
        response = await call_next(request)
        return response

    # Authenticate
    api_key = request.headers.get("X-API-Key", "")
    try:
        actor_name, role = authenticate(api_key)
    except HTTPException as exc:
        audit_log(request_id, "anonymous", "none", method, path,
                  exc.status_code)
        raise

    # Authorize
    permission = ENDPOINT_PERMISSIONS.get((method, path))
    if permission and permission[0] is not None:
        resource, action = permission
        try:
            authorize(role, resource, action)
        except HTTPException as exc:
            audit_log(request_id, actor_name, role, method, path,
                      exc.status_code)
            raise

    # Inject audit context into request state
    request.state.request_id = request_id
    request.state.trace_id = request.headers.get(
        "X-Trace-ID", str(uuid.uuid4())
    )
    request.state.actor = actor_name
    request.state.role = role

    response = await call_next(request)

    # Audit trail
    audit_log(
        request_id, actor_name, role, method, path,
        response.status_code,
    )

    response.headers["X-Request-ID"] = request_id
    return response


# ---------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------

@app.get("/health")
def health():
    from core.db import health_check
    db_ok = health_check()
    return {
        "status": "ok" if db_ok else "degraded",
        "db": "ok" if db_ok else "error",
    }


@app.post("/v1/etf/creation")
async def create_etf(data: dict, request: Request):
    data["request_id"] = request.state.request_id
    data["trace_id"] = request.state.trace_id
    data["actor"] = request.state.actor
    producer.send("creation-requests", data)
    return {
        "status": "submitted",
        "request_id": request.state.request_id,
    }


@app.post("/v1/settlement/approve")
async def approve_settlement(data: dict, request: Request):
    data["request_id"] = request.state.request_id
    data["trace_id"] = request.state.trace_id
    data["actor"] = request.state.actor
    data["action"] = "approve"
    producer.send("settlement-commands", data)
    return {
        "status": "approval_submitted",
        "request_id": request.state.request_id,
    }


@app.post("/v1/settlement/sign")
async def sign_settlement(data: dict, request: Request):
    data["request_id"] = request.state.request_id
    data["trace_id"] = request.state.trace_id
    data["actor"] = request.state.actor
    data["action"] = "sign"
    producer.send("settlement-commands", data)
    return {
        "status": "signing_submitted",
        "request_id": request.state.request_id,
    }


@app.get("/v1/ledger/balances")
async def get_balances(request: Request):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM account_balances WHERE balance != 0")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {"balances": [dict(r) for r in rows]}


@app.get("/v1/ledger/entries")
async def get_entries(request: Request, limit: int = 50):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, account, debit, credit,
               request_id, trace_id, actor, created_at
        FROM journal_entries
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (limit,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {"entries": [dict(r) for r in rows]}


@app.get("/v1/settlement/status")
async def settlement_status(request: Request):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, status, amount, currency, tx_hash,
               block_number, confirmations,
               created_at, confirmed_at
        FROM settlement_instructions
        ORDER BY created_at DESC
        LIMIT 50
        """,
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {"settlements": [dict(r) for r in rows]}
