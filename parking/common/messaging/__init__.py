"""The message bus: one abstraction, two transports.

    from parking.common.messaging import MemoryBus   # tests / simulation
    from parking.common.messaging import MqttBus      # real distributed run

`MqttBus` is exported lazily so importing this package never pulls in paho-mqtt
unless you actually ask for it.
"""
from .bus import Handler, MessageBus
from .memory_bus import MemoryBus

__all__ = ["MessageBus", "Handler", "MemoryBus", "MqttBus"]


def __getattr__(name: str):
    # PEP 562: import MqttBus (and paho) only on first access.
    if name == "MqttBus":
        from .mqtt_bus import MqttBus

        return MqttBus
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
