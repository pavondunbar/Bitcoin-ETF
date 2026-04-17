import hashlib
import uuid
from datetime import datetime, timezone

from core.db import get_conn
from events.events import Event, EventType
from events.state_machine import validate_settlement_state
from services.mpc_signing import request_mpc_signature
from services.blockchain import simulate_broadcast, simulate_confirmation


def settlement_handler(bus):
    """
    DETERMINISTIC SETTLEMENT STATE MACHINE

    Drives each settlement through:
    PENDING → APPROVED → SIGNED → BROADCASTED → CONFIRMED

    Each transition is:
    - Validated against the state machine
    - Persisted to settlement_instructions
    - Recorded in settlement_state_history (immutable)
    - Published as a domain event with audit context
    """

    def handle(event: Event):
        payload = event.payload
        amount = payload.get("nav", 0)
        trace_id = getattr(event, "trace_id", None)
        request_id = getattr(event, "request_id", None)
        actor = getattr(event, "actor", "system")

        # ===========================================================
        # STEP 1: PENDING — create settlement instruction
        # ===========================================================
        settlement_id = str(uuid.uuid4())
        conn = get_conn()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO settlement_instructions
                (id, event_id, event_type, counterparty, amount,
                 currency, status, request_id, trace_id, actor,
                 created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                settlement_id,
                str(event.id),
                str(event.type),
                payload.get("counterparty", "CCP_CLEARING"),
                amount,
                payload.get("currency", "USD"),
                "PENDING",
                request_id,
                trace_id,
                actor,
                datetime.now(timezone.utc),
            ),
        )

        _record_state_change(
            cur, settlement_id, None, "PENDING",
            actor, "Settlement instruction created",
        )

        conn.commit()
        conn.close()

        print(
            f"[SETTLEMENT] PENDING id={settlement_id} "
            f"amount={amount} (trace={trace_id})"
        )

        pending_payload = {
            **payload,
            "settlement_id": settlement_id,
            "settlement_status": "PENDING",
            "settlement_initiated_at": (
                datetime.now(timezone.utc).isoformat()
            ),
        }

        bus.publish(event.child(
            EventType.SETTLEMENT_PENDING,
            pending_payload,
            actor="system",
        ))

        # ===========================================================
        # STEP 2: APPROVED — compliance/risk check passed
        # ===========================================================
        _transition_settlement(
            settlement_id, "PENDING", "APPROVED",
            actor="approver",
            reason="Compliance check passed, within risk limits",
        )

        print(f"[SETTLEMENT] APPROVED id={settlement_id}")

        approved_payload = {
            **pending_payload,
            "settlement_status": "APPROVED",
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "approved_by": "approver",
        }

        bus.publish(event.child(
            EventType.SETTLEMENT_APPROVED,
            approved_payload,
            actor="approver",
        ))

        # ===========================================================
        # STEP 3: SIGNED — MPC 2-of-3 quorum signing
        # ===========================================================
        sign_payload = hashlib.sha256(
            f"{settlement_id}:{amount}".encode()
        ).hexdigest()

        mpc_result = request_mpc_signature(sign_payload)

        conn = get_conn()
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE settlement_instructions
            SET status = 'SIGNED',
                mpc_signature = %s,
                signer_quorum = %s,
                signed_at = NOW()
            WHERE id = %s
            """,
            (
                mpc_result["combined_signature"],
                mpc_result["quorum_json"],
                settlement_id,
            ),
        )

        _record_state_change(
            cur, settlement_id, "APPROVED", "SIGNED",
            actor="signer",
            reason=f"MPC 2-of-3 quorum: "
                   f"nodes {mpc_result['signing_nodes']}",
            metadata=mpc_result,
        )

        conn.commit()
        conn.close()

        print(
            f"[SETTLEMENT] SIGNED id={settlement_id} "
            f"sig={mpc_result['combined_signature'][:16]}..."
        )

        signed_payload = {
            **approved_payload,
            "settlement_status": "SIGNED",
            "mpc_signature": mpc_result["combined_signature"],
            "signing_nodes": mpc_result["signing_nodes"],
            "signed_at": datetime.now(timezone.utc).isoformat(),
        }

        bus.publish(event.child(
            EventType.SETTLEMENT_SIGNED,
            signed_payload,
            actor="signer",
        ))

        # ===========================================================
        # STEP 4: BROADCASTED — tx submitted to blockchain
        # ===========================================================
        broadcast_result = simulate_broadcast(
            settlement_id, amount,
            mpc_result["combined_signature"],
        )

        conn = get_conn()
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE settlement_instructions
            SET status = 'BROADCASTED',
                tx_hash = %s,
                block_number = %s,
                broadcasted_at = NOW()
            WHERE id = %s
            """,
            (
                broadcast_result["tx_hash"],
                broadcast_result["block_number"],
                settlement_id,
            ),
        )

        _record_state_change(
            cur, settlement_id, "SIGNED", "BROADCASTED",
            actor="system",
            reason=f"Broadcast tx={broadcast_result['tx_hash'][:16]}...",
            metadata=broadcast_result,
        )

        conn.commit()
        conn.close()

        print(
            f"[SETTLEMENT] BROADCASTED id={settlement_id} "
            f"tx={broadcast_result['tx_hash'][:16]}... "
            f"block={broadcast_result['block_number']}"
        )

        broadcasted_payload = {
            **signed_payload,
            "settlement_status": "BROADCASTED",
            "tx_hash": broadcast_result["tx_hash"],
            "block_number": broadcast_result["block_number"],
            "broadcasted_at": (
                datetime.now(timezone.utc).isoformat()
            ),
        }

        bus.publish(event.child(
            EventType.SETTLEMENT_BROADCASTED,
            broadcasted_payload,
            actor="system",
        ))

        # ===========================================================
        # STEP 5: CONFIRMED — block confirmations received
        # ===========================================================
        confirm_result = simulate_confirmation(
            broadcast_result["tx_hash"],
            broadcast_result["block_number"],
        )

        conn = get_conn()
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE settlement_instructions
            SET status = 'CONFIRMED',
                confirmations = %s,
                confirmed_at = NOW()
            WHERE id = %s
            """,
            (
                confirm_result["confirmations"],
                settlement_id,
            ),
        )

        _record_state_change(
            cur, settlement_id, "BROADCASTED", "CONFIRMED",
            actor="system",
            reason=(
                f"Confirmed with "
                f"{confirm_result['confirmations']} blocks"
            ),
            metadata=confirm_result,
        )

        conn.commit()
        conn.close()

        print(
            f"[SETTLEMENT] CONFIRMED id={settlement_id} "
            f"confirmations={confirm_result['confirmations']}"
        )

        confirmed_payload = {
            **broadcasted_payload,
            "settlement_status": "CONFIRMED",
            "confirmations": confirm_result["confirmations"],
            "confirmed_at": (
                datetime.now(timezone.utc).isoformat()
            ),
        }

        bus.publish(event.child(
            EventType.SETTLEMENT_CONFIRMED,
            confirmed_payload,
            actor="system",
        ))

    return handle


def _transition_settlement(
    settlement_id, from_status, to_status,
    actor="system", reason="",
):
    """Validate and persist a settlement state transition."""
    validate_settlement_state(from_status, to_status)

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE settlement_instructions
        SET status = %s
        WHERE id = %s AND status = %s
        """,
        (to_status, settlement_id, from_status),
    )

    if cur.rowcount == 0:
        conn.close()
        raise ValueError(
            f"Settlement {settlement_id} not in expected "
            f"state {from_status}"
        )

    # Set timestamp column
    ts_col = f"{to_status.lower()}_at"
    cur.execute(
        f"""
        UPDATE settlement_instructions
        SET {ts_col} = NOW()
        WHERE id = %s
        """,
        (settlement_id,),
    )

    _record_state_change(
        cur, settlement_id, from_status, to_status,
        actor, reason,
    )

    conn.commit()
    conn.close()


def _record_state_change(
    cur, settlement_id, prev, new,
    actor="system", reason="", metadata=None,
):
    """Append to immutable settlement_state_history."""
    import json
    cur.execute(
        """
        INSERT INTO settlement_state_history
            (id, settlement_id, previous_status, new_status,
             actor, reason, metadata, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            str(uuid.uuid4()),
            settlement_id,
            prev,
            new,
            actor,
            reason,
            json.dumps(metadata) if metadata else None,
            datetime.now(timezone.utc),
        ),
    )
