from smbus2 import SMBus, i2c_msg
import time

BUS  = 1
ADDR = 0x04
PIN  = 3  # D3

with SMBus(BUS) as bus:
    print("Watching motion on D3. Ctrl+C to stop.")
    prev = 0
    while True:
        # cmd=1 = digitalRead, response = 1 byte
        write = i2c_msg.write(ADDR, [1, 1, PIN, 0, 0])
        bus.i2c_rdwr(write)
        time.sleep(0.1)

        read = i2c_msg.read(ADDR, 1)
        bus.i2c_rdwr(read)
        value = list(read)[0]

        if value != prev:
            if value == 1:
                print("Motion detected!")
            else:
                print("No motion.")
            prev = value

        time.sleep(0.1)
