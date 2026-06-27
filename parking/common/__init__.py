"""Shared communication layer and contracts used by both nodes.

The three things every other module needs:

    from parking.common import topics                 # topic name catalog
    from parking.common import models as m            # message dataclasses
    from parking.common.messaging import MemoryBus    # the bus (or MqttBus)
"""
from . import models, topics
from .config import Settings, load_settings
from .messaging import MemoryBus, MessageBus

__all__ = ["topics", "models", "Settings", "load_settings", "MessageBus", "MemoryBus"]
