import json

def publish_to_kafka(event):
    print(f"[KAFKA MIRROR] {event.type} -> {json.dumps(event.payload)}")
