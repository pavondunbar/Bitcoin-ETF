class Event:
    def __init__(self, type, data):
        self.type = type
        self.data = data


class EventBus:
    def __init__(self):
        self.subscribers = {}

    def subscribe(self, event_type, handler):
        self.subscribers.setdefault(event_type, []).append(handler)

    def publish(self, event):
        print(f"[EVENT] {event.type} -> {event.data}")

        for handler in self.subscribers.get(event.type, []):
            handler(event.data)
