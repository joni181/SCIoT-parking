"""Print the standalone Mega rotary/LCD bring-up serial protocol."""
from __future__ import annotations

import argparse
import time

import serial


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="/dev/ttyACM0")
    parser.add_argument("--baud", type=int, default=9600)
    args = parser.parse_args()

    with serial.Serial(args.port, args.baud, timeout=1) as device:
        # Opening an Arduino USB serial port can reset the board.
        time.sleep(2)
        print(f"Monitoring {args.port} at {args.baud} baud. Ctrl-C to stop.")
        while True:
            line = device.readline().decode("utf-8", errors="replace").strip()
            if line:
                print(line)


if __name__ == "__main__":
    main()
