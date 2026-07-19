"""NfcReader: parsing the Mega's serial lines and debouncing a held card."""
from parking.common import models as m
from parking.common.messaging import MemoryBus
from parking.sensors import NfcReader


class FakeClock:
    def __init__(self, start: float = 0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _scans(bus: MemoryBus) -> list[m.NfcScanEvent]:
    events: list[m.NfcScanEvent] = []
    bus.subscribe_message(m.NfcScanEvent.TOPIC, events.append)
    return events


def test_publishes_on_first_scan():
    bus = MemoryBus()
    events = _scans(bus)
    clock = FakeClock()
    reader = NfcReader(bus, reader=m.READER_GATE, firmware_reader=1, clock=clock)

    reader._on_line("NFC reader=1 uid=DEADBEEF")

    assert [e.uid for e in events] == ["DEADBEEF"]


def test_ignores_repeated_line_for_a_held_card():
    """A held card can make the firmware republish the same UID a few times
    in quick succession (see NfcReader's docstring); only the first counts."""
    bus = MemoryBus()
    events = _scans(bus)
    clock = FakeClock()
    reader = NfcReader(bus, reader=m.READER_GATE, firmware_reader=1, clock=clock, debounce_s=2.0)

    reader._on_line("NFC reader=1 uid=DEADBEEF")
    clock.advance(0.3)
    reader._on_line("NFC reader=1 uid=DEADBEEF")
    clock.advance(0.3)
    reader._on_line("NFC reader=1 uid=DEADBEEF")

    assert [e.uid for e in events] == ["DEADBEEF"]


def test_republishes_the_same_uid_after_the_debounce_window():
    bus = MemoryBus()
    events = _scans(bus)
    clock = FakeClock()
    reader = NfcReader(bus, reader=m.READER_GATE, firmware_reader=1, clock=clock, debounce_s=2.0)

    reader._on_line("NFC reader=1 uid=DEADBEEF")
    clock.advance(2.5)
    reader._on_line("NFC reader=1 uid=DEADBEEF")

    assert [e.uid for e in events] == ["DEADBEEF", "DEADBEEF"]


def test_different_uid_publishes_immediately_even_within_the_window():
    bus = MemoryBus()
    events = _scans(bus)
    clock = FakeClock()
    reader = NfcReader(bus, reader=m.READER_GATE, firmware_reader=1, clock=clock, debounce_s=2.0)

    reader._on_line("NFC reader=1 uid=DEADBEEF")
    clock.advance(0.1)
    reader._on_line("NFC reader=1 uid=CAFEBABE")

    assert [e.uid for e in events] == ["DEADBEEF", "CAFEBABE"]


def test_ignores_lines_for_a_different_firmware_reader():
    bus = MemoryBus()
    events = _scans(bus)
    reader = NfcReader(bus, reader=m.READER_GATE, firmware_reader=1)

    reader._on_line("NFC reader=2 uid=DEADBEEF")

    assert events == []
