"""Watch the photoresistor readings live and help pick each spot's threshold.

Prints every `LIGHT sensor=<label> raw=<n>` line from the Mega, plus a
running min/max/midpoint *per sensor*, so you can watch a spot empty vs.
covered and find a raw ADC value that reliably separates "occupied" from
"free" - see `parking.sensors.OccupancySensor`'s `threshold` and
`occupied_below_threshold`. Each spot's photoresistor is wired/mounted
independently, so calibrate each one separately.

    python3 hardware/pi/bringup/test_photoresistor_threshold.py                       # watch all 4
    python3 hardware/pi/bringup/test_photoresistor_threshold.py --sensor photoresistor_a12  # just P1
    python3 hardware/pi/bringup/test_photoresistor_threshold.py --port /dev/ttyACM1
"""
from __future__ import annotations

import argparse
import re
import time

import serial

_LIGHT_LINE = re.compile(r"^LIGHT sensor=(?P<sensor>\S+) raw=(?P<raw>\d+)$")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="/dev/ttyACM0")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument(
        "--sensor",
        default=None,
        help="only watch one sensor label (e.g. photoresistor_a12); default: all of them",
    )
    args = parser.parse_args()

    stats: dict[str, tuple[int, int]] = {}  # label -> (lowest, highest)

    with serial.Serial(args.port, args.baud, timeout=1) as device:
        # Opening an Arduino USB serial port can reset the board.
        time.sleep(2)
        print(f"Watching {args.port} at {args.baud} baud. Ctrl-C to stop.")
        print("Cover/uncover a spot; that sensor's min/max/midpoint update live.\n")
        while True:
            line = device.readline().decode("utf-8", errors="replace").strip()
            match = _LIGHT_LINE.match(line)
            if not match:
                continue
            label = match.group("sensor")
            if args.sensor is not None and label != args.sensor:
                continue
            raw = int(match.group("raw"))
            lowest, highest = stats.get(label, (raw, raw))
            lowest, highest = min(lowest, raw), max(highest, raw)
            stats[label] = (lowest, highest)
            midpoint = (lowest + highest) // 2
            print(f"{label:20} raw={raw:4d}  min={lowest:4d}  max={highest:4d}  midpoint={midpoint:4d}")


if __name__ == "__main__":
    main()
