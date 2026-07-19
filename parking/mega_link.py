"""Shared serial transport to the bring-up Mega controller.

`hardware/mega/firmware/mega_controller/mega_controller.c` exposes a single
USB-serial connection that carries several independent streams at once: NFC
scans, distance readings, light readings, and (as a write) gate open/close
commands. Each of those needs the same port, so exactly one `MegaLink` owns
the connection and fans lines out to every registered listener; drivers never
open the port themselves.

`pyserial` (only listed in `requirements/pi.txt`) is imported lazily so
importing this module elsewhere stays hardware-free.
"""
from __future__ import annotations

import threading
import time
from typing import Callable, List, Optional


#: Stable path keyed to the board's USB serial number (from `hardware/pinmap.yaml`),
#: so it doesn't change when the Mega re-enumerates as a different /dev/ttyACM<N>
#: on every reset/reflash/replug.
DEFAULT_PORT = (
    "/dev/serial/by-id/"
    "usb-Arduino__www.arduino.cc__Arduino_Mega_ADK_6493633393635170A1D2-if00"
)


class MegaLink:
    """Owns the Mega's serial port: one reader thread, thread-safe writes.

    Both directions self-heal: a read or write failure (e.g. the board
    re-enumerating after a reflash/replug) closes and reopens the port rather
    than leaving `send()` silently broken forever or the reader thread stuck
    retrying a dead connection - the port is opened on `self._port`, so this
    only recovers automatically when that's the stable `by-id` path; a raw
    `/dev/ttyACM<N>` override won't resolve to wherever the board actually
    lands after it moves.
    """

    def __init__(self, port: str = DEFAULT_PORT, baudrate: int = 9600) -> None:
        self._port = port
        self._baudrate = baudrate
        self._serial = None
        self._io_lock = threading.Lock()
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
        self._stop_event.clear()
        self._open()
        self._thread = threading.Thread(target=self._run, name="mega-link", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        with self._io_lock:
            if self._serial is not None:
                self._serial.close()
                self._serial = None

    def send(self, line: str) -> None:
        """Write one command line to the Mega (e.g. "GATE OPEN")."""
        if self._write(line):
            return
        print("[mega-link] write failed, reconnecting")
        self._reconnect()
        if not self._write(line):
            print(f"[mega-link] write retry failed, command dropped: {line!r}")

    def _write(self, line: str) -> bool:
        with self._io_lock:
            device = self._serial
        if device is None:
            return False
        try:
            device.write((line + "\r\n").encode("utf-8"))
            return True
        except Exception as exc:
            print(f"[mega-link] serial write failed: {exc!r}")
            return False

    def _open(self) -> None:
        import serial  # deferred: only required on the Pi with real hardware

        device = serial.Serial(self._port, self._baudrate, timeout=1)
        with self._io_lock:
            self._serial = device

    def _reconnect(self) -> None:
        with self._io_lock:
            stale = self._serial
            self._serial = None
        if stale is not None:
            try:
                stale.close()
            except Exception:
                pass
        time.sleep(0.5)
        try:
            self._open()
            print(f"[mega-link] reconnected to {self._port}")
        except Exception as exc:
            print(f"[mega-link] reconnect failed: {exc!r}")

    def _run(self) -> None:
        # Both driver and I/O errors are isolated here: every listener shares this
        # one thread (DistanceSensor + NfcReader alike), so an unhandled exception
        # from a bad line or a transient serial hiccup would otherwise silently
        # kill line dispatch for all of them at once, not just the one at fault.
        while not self._stop_event.is_set():
            with self._io_lock:
                device = self._serial
            if device is None:
                time.sleep(0.5)
                continue
            try:
                raw = device.readline().decode("utf-8", errors="replace").strip()
            except Exception as exc:
                print(f"[mega-link] serial read failed, reconnecting: {exc!r}")
                self._reconnect()
                continue
            if not raw:
                continue
            for listener in self._listeners:
                try:
                    listener(raw)
                except Exception as exc:
                    print(f"[mega-link] listener failed on line {raw!r}: {exc!r}")
