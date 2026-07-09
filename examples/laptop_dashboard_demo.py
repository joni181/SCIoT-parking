"""Run the complete laptop dashboard with a guided simulated Pi.

    python examples/laptop_dashboard_demo.py

This single command starts a private MQTT broker, the real laptop services, a
second MQTT client that behaves like the Pi, and the browser dashboard. No Pi
or hardware is required.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from parking.simulation import GuidedScenarioController, MqttDemoSystem  # noqa: E402
from parking.visualization import DashboardView  # noqa: E402


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _wait_for_broker(process: subprocess.Popen, port: int, timeout: float = 8.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                "The local MQTT broker exited during startup. "
                "Run: pip install -r requirements/laptop.txt"
            )
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("Timed out while starting the local MQTT broker")


def main() -> None:
    broker_port = _free_port()
    dashboard_port = _free_port()
    env = dict(
        os.environ,
        PARKING_BROKER_BIND="127.0.0.1",
        PARKING_BROKER_PORT=str(broker_port),
        PYTHONUNBUFFERED="1",
    )
    broker = subprocess.Popen(
        [sys.executable, str(REPO_ROOT / "deploy" / "broker.py")],
        cwd=str(REPO_ROOT),
        env=env,
    )
    controller = None
    dashboard = None
    try:
        _wait_for_broker(broker, broker_port)
        controller = GuidedScenarioController(
            lambda: MqttDemoSystem("127.0.0.1", broker_port)
        )
        dashboard = DashboardView(
            controller.source,
            host="127.0.0.1",
            port=dashboard_port,
            open_browser=os.environ.get("PARKING_DASHBOARD_OPEN_BROWSER", "1").lower()
            not in ("0", "false", "no", "off"),
            demo_controller=controller,
        )
        dashboard.start()
        print(f"[demo] dashboard: {dashboard.url}")
        print("[demo] choose a scenario in the browser. Press Ctrl-C here to stop.")
        while True:
            time.sleep(1.0)
    except ImportError as exc:
        raise SystemExit(
            "Dashboard demo dependencies are missing. "
            "Run: pip install -r requirements/laptop.txt"
        ) from exc
    except RuntimeError as exc:
        if "dependencies are missing" in str(exc) or "requirements/laptop.txt" in str(exc):
            raise SystemExit(str(exc)) from exc
        raise
    except KeyboardInterrupt:
        print("\n[demo] stopping...")
    finally:
        if dashboard is not None:
            dashboard.stop()
        if controller is not None:
            controller.close()
        if broker.poll() is None:
            broker.terminate()
            try:
                broker.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                broker.kill()
                broker.wait(timeout=2.0)


if __name__ == "__main__":
    main()
