
from kafka import KafkaConsumer, KafkaProducer
import json

consumer = KafkaConsumer(
    "creation_requests",
    bootstrap_servers="kafka:9092",
    value_deserializer=lambda m: json.loads(m.decode())
)

producer = KafkaProducer(
    bootstrap_servers="kafka:9092",
    value_serializer=lambda v: json.dumps(v).encode()
)

for msg in consumer:
    cash = msg.value["cash"]
    producer.send("execution_requests", {"cash": cash})
    print(f"Issuer forwarded {cash}")
