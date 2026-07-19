"""StatusLed: turning LotFullCommand into "LED ON"/"LED OFF" over MegaLink."""
from parking.actuators import StatusLed
from parking.common import models as m
from parking.common.messaging import MemoryBus


class FakeLink:
    def __init__(self):
        self.sent: list[str] = []

    def send(self, line: str) -> None:
        self.sent.append(line)


def test_sends_led_on_when_lot_is_full():
    bus = MemoryBus()
    link = FakeLink()
    led = StatusLed(bus, link)
    led.start()

    bus.publish_message(m.LotFullCommand(full=True))

    assert link.sent == ["LED ON"]


def test_sends_led_off_when_lot_is_not_full():
    bus = MemoryBus()
    link = FakeLink()
    led = StatusLed(bus, link)
    led.start()

    bus.publish_message(m.LotFullCommand(full=False))

    assert link.sent == ["LED OFF"]


def test_no_link_is_a_safe_no_op():
    bus = MemoryBus()
    led = StatusLed(bus)  # no link, matches simulated/no-hardware runs
    led.start()

    bus.publish_message(m.LotFullCommand(full=True))  # must not raise
