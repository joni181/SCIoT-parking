"""IoT input sensor drivers (Raspberry Pi).

    from parking.sensors import Sensor                  # the interface
    from parking.sensors import OccupancySensor, ...    # real drivers (skeletons)

Every driver implements `Sensor`: it reads a device and publishes the matching
event from `parking.common.models`. `SimulatedSensors` in `parking.simulation`
is the hardware-free stand-in used by the tests and the demo.
"""
from .base import Sensor
from .drivers import DistanceSensor, DurationDial, NfcReader, OccupancySensor

__all__ = ["Sensor", "OccupancySensor", "NfcReader", "DurationDial", "DistanceSensor"]
