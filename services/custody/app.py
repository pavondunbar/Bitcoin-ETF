
from kafka import KafkaConsumer
import json

consumer = KafkaConsumer(
    "execution-fills",
    bootstrap_servers="kafka:9092",
    value_deserializer=lambda m: json.loads(m.decode())
)

balance = 0

for msg in consumer:
    btc = msg.value["btc"]
    balance += btc
    print(f"Custody balance {balance}")
