import serial
import time

ser = serial.Serial('/dev/ttyACM0', 9600, timeout=1)
time.sleep(2)

print("Reading sensors. Ctrl+C to stop.")
while True:
    line = ser.readline().decode().strip()
    if line == "BUTTON":
        print("Button pressed!")
    elif line.startswith("LIGHT:"):
        parts = dict(p.split(':') for p in line.split(','))
        print(f"Light: {parts['LIGHT']}  Rotary: {parts['ROTARY']}")
