"""Shared serial transport to the bring-up Mega controller.

`hardware/mega/firmware/rotary_lcd_bringup/mega_controller.c` exposes a single
USB-serial connection that carries several independent streams at once: NFC
scans, distance readings, and (as a write) gate open/close commands. Each of
those needs the same port, so exactly one `MegaLink` owns the connection and
fans lines out to every registered listener; drivers never open the port
themselves.

`pyserial` (only listed in `requirements/pi.txt`) is imported inside `start()`
so importing this module elsewhere stays hardware-free.
"""
from __future__ import annotations

import threading
import time
from typing import Callable, List, Optional


class MegaLink:
    """Owns the Mega's serial port: one reader thread, thread-safe writes."""

    def __init__(self, port: str = "/dev/ttyACM0", baudrate: int = 9600) -> None:
        self._port = port
        self._baudrate = baudrate
        self._serial = None
        self._write_lock = threading.Lock()
        self._listeners: List[Callable[[str], None]] = []
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def add_listener(self, callback: Callable[[str], None]) -> None:
        """Register a line callback. Call before `start()`."""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[str], None]) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        import serial  # deferred: only required on the Pi with real hardware

        self._stop_event.clear()
        self._serial = serial.Serial(self._port, self._baudrate, timeout=1)
        self._thread = threading.Thread(target=self._run, name="mega-link", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._serial is not None:
            self._serial.close()
            self._serial = None

    def send(self, line: str) -> None:
        """Write one command line to the Mega (e.g. "GATE OPEN")."""
        with self._write_lock:
            self._serial.write((line + "\r\n").encode("utf-8"))

    def _run(self) -> None:
        # Both driver and I/O errors are isolated here: every listener shares this
        # one thread (DistanceSensor + NfcReader alike), so an unhandled exception
        # from a bad line or a transient serial hiccup would otherwise silently
        # kill line dispatch for all of them at once, not just the one at fault.
        while not self._stop_event.is_set():
            try:
                raw = self._serial.readline().decode("utf-8", errors="replace").strip()
            except Exception as exc:
                print(f"[mega-link] serial read failed, retrying: {exc!r}")
                time.sleep(0.5)
                continue
            if not raw:
                continue
            for listener in self._listeners:
                try:
                    listener(raw)
                except Exception as exc:
                    print(f"[mega-link] listener failed on line {raw!r}: {exc!r}")
