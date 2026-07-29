import unittest

from Core.realtime.event_bus import EventBus


class TestEventBus(unittest.TestCase):
    def test_subscribers_receive_published_events(self):
        bus = EventBus()
        received = []

        def handler(payload):
            received.append(payload)

        bus.subscribe("game.started", handler)
        bus.publish("game.started", {"turn": "white"})

        self.assertEqual(received, [{"turn": "white"}])

    def test_subscribers_can_unsubscribe(self):
        bus = EventBus()
        received = []

        def handler(payload):
            received.append(payload)

        token = bus.subscribe("game.ended", handler)
        bus.unsubscribe(token)
        bus.publish("game.ended", {"winner": "black"})

        self.assertEqual(received, [])


if __name__ == "__main__":
    unittest.main()
