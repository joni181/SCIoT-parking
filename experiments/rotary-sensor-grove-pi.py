from smbus2 import SMBus, i2c_msg
import time

BUS  = 1
ADDR = 0x04
PIN  = 1  # A1

with SMBus(BUS) as bus:
    print("Reading rotary sensor on A1. Ctrl+C to stop.")
    while True:
        write = i2c_msg.write(ADDR, [1, 3, PIN, 0, 0])
        bus.i2c_rdwr(write)
        time.sleep(0.5)

        read = i2c_msg.read(ADDR, 3)
        bus.i2c_rdwr(read)
        data = list(read)
        value = (data[1] << 8) | data[2]
        print(f"Rotary value: {value}")
        time.sleep(0.2)
