# sensors  [Raspberry Pi]

Hardware drivers for the IoT input devices. Each sensor publishes its readings as
events on the bus; no other module touches the hardware directly.

Devices: NFC card reader (gate + checkout), light sensors (parking/buffer occupancy),
motion sensor (vehicle at gate), rotary angle sensor (expected parking duration).

**Interface:** [`Sensor`](base.py) (a `Component`). Drivers (skeletons) in
[`drivers.py`](drivers.py); hardware-free stand-in is `SimulatedSensors` in
[`../simulation/`](../simulation/README.md).
