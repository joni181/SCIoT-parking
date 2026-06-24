from smbus2 import SMBus
import time

BUS  = 1
ADDR = 0x04

def send(bus, cmd, pin, val):
    bus.write_i2c_block_data(ADDR, 1, [cmd, pin, val, 0])
    time.sleep(0.05)

LED = 4

with SMBus(BUS) as bus:
    send(bus, 5, LED, 1)       # pinMode OUTPUT
    time.sleep(0.5)
    print("Blinking on D%d. Ctrl+C to stop." % LED)
    while True:
        send(bus, 2, LED, 1)   # digitalWrite HIGH
        time.sleep(1)
        send(bus, 2, LED, 0)   # digitalWrite LOW
        time.sleep(1)
