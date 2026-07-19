"""Watch the buffer's photoresistor readings live and help pick a threshold.

Prints every `LIGHT sensor=photoresistor_a15 raw=<n>` line from the Mega,
plus a running min/max/midpoint, so you can watch the buffer empty vs.
covered and find a raw ADC value that reliably separates "occupied" from
"free" - see `parking.sensors.OccupancySensor`'s `threshold` and
`occupied_below_threshold`.

    python3 hardware/pi/bringup/test_photoresistor_threshold.py
    python3 hardware/pi/bringup/test_photoresistor_threshold.py --port /dev/ttyACM1
"""
from __future__ import annotations

import argparse
import re
import time

import serial

_LIGHT_LINE = re.compile(r"^LIGHT sensor=\S+ raw=(?P<raw>\d+)$")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="/dev/ttyACM0")
    parser.add_argument("--baud", type=int, default=9600)
    args = parser.parse_args()

    lowest: int | None = None
    highest: int | None = None

    with serial.Serial(args.port, args.baud, timeout=1) as device:
        # Opening an Arduino USB serial port can reset the board.
        time.sleep(2)
        print(f"Watching {args.port} at {args.baud} baud. Ctrl-C to stop.")
        print("Cover/uncover the buffer a few times; min/max/midpoint update live.\n")
        while True:
            line = device.readline().decode("utf-8", errors="replace").strip()
            match = _LIGHT_LINE.match(line)
            if not match:
                continue
            raw = int(match.group("raw"))
            lowest = raw if lowest is None else min(lowest, raw)
            highest = raw if highest is None else max(highest, raw)
            midpoint = (lowest + highest) // 2
            print(f"raw={raw:4d}  min={lowest:4d}  max={highest:4d}  midpoint={midpoint:4d}")


if __name__ == "__main__":
    main()
