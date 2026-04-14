
from kafka import KafkaConsumer, KafkaProducer
import json, random

consumer = KafkaConsumer(
    "execution_requests",
    bootstrap_servers="kafka:9092",
    value_deserializer=lambda m: json.loads(m.decode())
)

producer = KafkaProducer(
    bootstrap_servers="kafka:9092",
    value_serializer=lambda v: json.dumps(v).encode()
)

for msg in consumer:
    cash = msg.value["cash"]
    btc = cash / (65000 * (1 + random.uniform(0.001,0.005)))
    producer.send("execution_fills", {"btc": btc})
    print(f"Execution bought {btc}")
