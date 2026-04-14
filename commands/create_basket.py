def handle_create_basket(command, bus):
    bus.publish(Event(
        type=EventType.TRADE_CREATED,
        payload=command
    ))
