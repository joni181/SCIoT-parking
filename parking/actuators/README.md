# actuators  [Raspberry Pi]

Hardware drivers for the physical actuators. Subscribe to actuator commands on the bus
and drive the devices.

Devices: gate (servo motor), parking/buffer indicator (LED), vehicle motion
(human-simulated in the demo).

**Interface:** [`Actuator`](base.py) (a `Component`). Drivers (skeletons) in
[`drivers.py`](drivers.py) currently subscribe but do not drive hardware; the test
double is `RecordingActuators` in
[`../simulation/`](../simulation/README.md).
