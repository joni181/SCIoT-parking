#!/usr/bin/env python3
"""Quick RFID test: prints the UID of any card held near the RC522 reader."""

import signal
import sys

import RPi.GPIO as GPIO

import mfrc522

reader = mfrc522.MFRC522()

print("RFID reader ready. Hold a card near the sensor. Press Ctrl-C to exit.\n")


def _cleanup(sig=None, frame=None):
    GPIO.cleanup()
    sys.exit(0)


signal.signal(signal.SIGINT, _cleanup)

while True:
    status, _ = reader.request()
    if status != mfrc522.MI_OK:
        continue

    status, uid = reader.anticoll()
    if status != mfrc522.MI_OK:
        continue

    print(f"Card detected  UID: {reader.uid_to_str(uid)}  (raw: {uid[:4]})")
