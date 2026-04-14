def check_idempotency(db, key):
    existing = db.fetch("SELECT * FROM idempotency WHERE key=%s", (key,))
    if existing:
        return existing[0]["response"]
    return None

def store_idempotency(db, key, response):
    db.execute(
        "INSERT INTO idempotency(key, response) VALUES(%s,%s)",
        (key, response)
    )
