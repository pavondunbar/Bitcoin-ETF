
from kafka import KafkaConsumer
import json

consumer = KafkaConsumer(
    "execution-fills",
    bootstrap_servers="kafka:9092",
    value_deserializer=lambda m: json.loads(m.decode())
)

reserves = 0
shares = 1000000

for msg in consumer:
    reserves += msg.value["btc"]
    nav = (65000 * reserves) / shares
    print(f"NAV: {nav}")
