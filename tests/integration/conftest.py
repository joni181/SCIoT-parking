"""Fixtures for the integration tests - a real MQTT broker on a free port.

The broker is the same pure-Python `amqtt` server that `deploy/broker.py` runs
on the laptop, started here in a background thread so the tests connect to it
exactly like the live nodes do (real TCP, real paho clients).

The test modules themselves `importorskip("amqtt")`, so the core (MemoryBus)
suite still runs with zero dependencies.
"""
from __future__ import annotations

import asyncio
import logging
import socket
import threading

import pytest

# amqtt is chatty at INFO/DEBUG; keep test output readable.
for _name in ("amqtt", "transitions", "asyncio"):
    logging.getLogger(_name).setLevel(logging.WARNING)


def free_port() -> int:
    """Grab an unused localhost TCP port (closed immediately, then reused)."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def mqtt_broker():
    """Start an amqtt broker on a free port; yield the port; shut it down."""
    from amqtt.broker import Broker

    port = free_port()
    ready = threading.Event()
    state: dict = {}

    def run() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _start() -> None:
            broker = Broker(
                {
                    "listeners": {"default": {"type": "tcp", "bind": f"127.0.0.1:{port}"}},
                    "sys_interval": 0,
                    "auth": {"allow-anonymous": True},
                }
            )
            state["broker"] = broker
            await broker.start()
            ready.set()

        loop.run_until_complete(_start())
        state["loop"] = loop
        loop.run_forever()

    threading.Thread(target=run, daemon=True).start()
    assert ready.wait(15), "amqtt broker failed to start"

    yield port

    # Graceful shutdown: stop the broker on its own loop, then stop the loop.
    loop = state.get("loop")
    broker = state.get("broker")
    if loop is not None and broker is not None:
        try:
            asyncio.run_coroutine_threadsafe(broker.shutdown(), loop).result(timeout=5)
        except Exception:
            pass
        loop.call_soon_threadsafe(loop.stop)
