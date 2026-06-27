"""Hardware-free stand-ins for exercising the message flow.

These let the team build and test everything *before* the Raspberry Pi and the
Grove/RC522 hardware are wired up:

  * `SimulatedSensors`   - publishes the same events the real Pi drivers would.
  * `RecordingActuators` - subscribes to actuator commands and records them
                           instead of driving a motor / LED.
  * `ReactiveGateController`, `OccupancyTracker` - illustrative control/consumer
                           logic, used by the demo and the scenario tests.

Pair them with `parking.common.messaging.MemoryBus` for deterministic runs.
"""
from .controllers import OccupancyTracker, ReactiveGateController
from .devices import RecordingActuators, SimulatedSensors

__all__ = [
    "SimulatedSensors",
    "RecordingActuators",
    "ReactiveGateController",
    "OccupancyTracker",
]
