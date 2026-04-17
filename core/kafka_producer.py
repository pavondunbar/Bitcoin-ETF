import json
from kafka import KafkaProducer


producer = KafkaProducer(
    bootstrap_servers="kafka:9092",
    key_serializer=lambda k: k.encode("utf-8") if k else None,
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
)


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
    # NORMALIZE EVENT
    # ---------------------------------------------------------
    payload = (
        event.payload
        if hasattr(event, "payload")
        else event
    )

    event_type = (
        str(event.type)
        if hasattr(event, "type")
        else event.get("type", "UNKNOWN")
    )

    message = {
        "type": event_type,
        "payload": payload,
    }

    # ---------------------------------------------------------
    # SEND TO KAFKA (OUTBOX RELAY ONLY)
    # ---------------------------------------------------------
    producer.send(
        "event_log",
        key=key,
        value=message,
    )

    producer.flush()

    print(f"[KAFKA] published {event_type}")


def publish_to_dlq(message):
    """
    DEAD LETTER QUEUE

    Messages that exceed max retries are routed here
    for manual inspection and replay.
    """
    producer.send(
        "dlq_default",
        value=message,
    )
    producer.flush()

    print(
        f"[KAFKA-DLQ] routed {message.get('event_type', '?')} "
        f"to dlq_default"
    )
