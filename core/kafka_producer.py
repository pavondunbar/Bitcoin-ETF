import os
import json
from kafka import KafkaProducer


KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")

_producer = None


def _get_producer():
    """Lazy-init the KafkaProducer on first use.

    Avoids NoBrokersAvailable at import time when Kafka
    hasn't finished starting yet.
    """
    global _producer
    if _producer is None:
        _producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            key_serializer=(
                lambda k: k.encode("utf-8") if k else None
            ),
            value_serializer=(
                lambda v: json.dumps(v).encode("utf-8")
            ),
        )
    return _producer


def publish_to_kafka(event):
    """
    OUTBOX RELAY TARGET

    This is ONLY called by:
        outbox_worker.py

    NOT by EventBus (important architectural rule)
    """

    # ---------------------------------------------------------
    # IDENTITY KEY (CRITICAL FOR DEDUP IN KAFKA)
    # ---------------------------------------------------------
    key = getattr(event, "idempotency_key", None)

    if key is None and isinstance(event, dict):
        key = event.get("idempotency_key")

    # ---------------------------------------------------------
    # NORMALIZE EVENT (supports both objects and dicts)
    # ---------------------------------------------------------
    if hasattr(event, "payload"):
        payload = event.payload
    elif isinstance(event, dict):
        payload = event.get("payload", event)
    else:
        payload = event

    if hasattr(event, "type"):
        event_type = str(event.type)
    elif isinstance(event, dict):
        event_type = event.get("type", "UNKNOWN")
    else:
        event_type = "UNKNOWN"

    message = {
        "type": event_type,
        "payload": payload,
    }

    # ---------------------------------------------------------
    # SEND TO KAFKA (OUTBOX RELAY ONLY)
    # ---------------------------------------------------------
    _get_producer().send(
        "event-log",
        key=key,
        value=message,
    )

    _get_producer().flush()

    print(f"[KAFKA] published {event_type}")


def publish_to_dlq(message):
    """
    DEAD LETTER QUEUE

    Messages that exceed max retries are routed here
    for manual inspection and replay.
    """
    _get_producer().send(
        "dlq-default",
        value=message,
    )
    _get_producer().flush()

    print(
        f"[KAFKA-DLQ] routed {message.get('event_type', '?')} "
        f"to dlq-default"
    )
