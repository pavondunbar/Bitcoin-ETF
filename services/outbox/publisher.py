import json

def publish(db, kafka):
    rows = db.fetch("SELECT * FROM outbox WHERE sent=false")

    for r in rows:
        kafka.produce(r["topic"], json.dumps(r["payload"]))
        db.execute("UPDATE outbox SET sent=true WHERE id=%s", (r["id"],))
