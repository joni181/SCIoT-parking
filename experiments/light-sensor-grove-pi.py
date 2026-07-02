from smbus2 import SMBus, i2c_msg
import time

BUS  = 1
ADDR = 0x04

with SMBus(BUS) as bus:
    print("Reading light sensor on A0. Ctrl+C to stop.")
    while True:
        # Write: 5 bytes — dummy(1), cmd(3=analogRead), pin(0=A0), data, data
        write = i2c_msg.write(ADDR, [1, 3, 0, 0, 0])
        bus.i2c_rdwr(write)
        time.sleep(0.5)

        # Read: 3 bytes — first unused, then 2 bytes value
        read = i2c_msg.read(ADDR, 3)
        bus.i2c_rdwr(read)
        data = list(read)
        value = (data[1] << 8) | data[2]
        print(f"Light value: {value}")
        time.sleep(1)
