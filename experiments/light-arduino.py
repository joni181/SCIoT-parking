import serial
import time

ser = serial.Serial('/dev/ttyACM0', 9600, timeout=1)
time.sleep(2)  # wait for Arduino to reset after serial connect

print("Reading light sensor. Ctrl+C to stop.")
while True:
    line = ser.readline().decode().strip()
    if line:
        print(f"Light value: {line}")
