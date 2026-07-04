"""End-to-end smoke test of the *actual* deployment, as separate OS processes.

This is the closest mirror of live operation: it launches the real
`deploy/broker.py`, `apps/laptop_node.py` and `apps/pi_node.py` as three
independent processes (just like running them on the laptop + the Pi), pointed
at a free port via the same env vars you'd use in the field, and asserts the
Pi's events show up at the laptop and the gate command comes back.

Unlike test_live_mqtt.py (same process, real broker), this also exercises the
app entrypoints themselves: config loading, `__main__` wiring, and process
startup. It's slower, so it's marked `integration`.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("amqtt")
pytest.importorskip("paho.mqtt.client")

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_three_real_processes_exchange_over_broker():
    port = _free_port()
    env = dict(
        os.environ,
        PARKING_BROKER_HOST="127.0.0.1",
        PARKING_BROKER_BIND="127.0.0.1",
        PARKING_BROKER_PORT=str(port),
        PYTHONUNBUFFERED="1",
    )

    def launch(rel_path: str) -> subprocess.Popen:
        return subprocess.Popen(
            [sys.executable, rel_path],
            cwd=str(REPO_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    broker = launch("deploy/broker.py")
    time.sleep(3.0)  # let the broker bind
    laptop = launch("apps/laptop_node.py")
    time.sleep(2.0)  # let the laptop connect + subscribe

    try:
        pi = subprocess.run(
            [sys.executable, "apps/pi_node.py"],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=40,
        )
        time.sleep(1.5)  # let the last messages reach the laptop
    finally:
        laptop.terminate()
        try:
            laptop_out, _ = laptop.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            laptop.kill()
            laptop_out, _ = laptop.communicate()
        broker.terminate()
        try:
            broker.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            broker.kill()

    # The Pi side ran its scenario and drove the gate.
    assert "gate motor -> open" in pi.stdout, pi.stdout
    assert "gate motor -> close" in pi.stdout, pi.stdout

    # The laptop side received the Pi's events + the resulting command over MQTT.
    assert "[laptop] connected to broker" in laptop_out, laptop_out
    assert "occupancy" in laptop_out and "P1" in laptop_out, laptop_out
    assert "gate_cmd" in laptop_out, laptop_out
