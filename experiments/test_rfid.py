#!/usr/bin/env python3
"""RFID test: prints the UID of any card detected by either RC522 reader.

Single reader:  python3 test_rfid.py
Dual readers:   python3 test_rfid.py --dual

Wiring (dual):
  Both readers share SCK (pin23), MOSI (pin19), MISO (pin21).
  Reader 1 SDA → CE0 (pin24/GPIO8),  RST → GPIO25 (pin22)
  Reader 2 SDA → CE1 (pin26/GPIO7),  RST → GPIO24 (pin18)
"""

import argparse
import signal
import sys

import RPi.GPIO as GPIO

import mfrc522

parser = argparse.ArgumentParser()
parser.add_argument("--dual", action="store_true", help="Use two readers")
args = parser.parse_args()

readers = [mfrc522.MFRC522(rst_pin=25, spi_bus=0, spi_device=0)]
if args.dual:
    readers.append(mfrc522.MFRC522(rst_pin=24, spi_bus=0, spi_device=1))

print(f"{'Dual' if args.dual else 'Single'}-reader mode. Hold a card near a sensor. Ctrl-C to exit.\n")


def _cleanup(sig=None, frame=None):
    GPIO.cleanup()
    sys.exit(0)


signal.signal(signal.SIGINT, _cleanup)

while True:
    for i, reader in enumerate(readers):
        status, _ = reader.request()
        if status != mfrc522.MI_OK:
            continue

        status, uid = reader.anticoll()
        if status != mfrc522.MI_OK:
            continue

        label = f"Reader {i + 1}"
        print(f"{label}  UID: {reader.uid_to_str(uid)}  (raw: {uid[:4]})")
