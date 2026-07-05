"""Physical actuator drivers (Raspberry Pi).

    from parking.actuators import Actuator              # the interface
    from parking.actuators import GateMotor, ...        # real drivers (skeletons)

Every driver implements `Actuator`: it subscribes to a command topic from
`parking.common.models` and drives a device. `RecordingActuators` in
`parking.simulation` is the hardware-free test double.
"""
from .base import Actuator
from .drivers import BufferLed, GateMotor, GateServo, VehicleMover

__all__ = ["Actuator", "GateServo", "GateMotor", "BufferLed", "VehicleMover"]
