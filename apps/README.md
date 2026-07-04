# apps - runnable entrypoints

Composition roots that wire modules into the actual processes you launch. This is the
only place deployment is decided. Each entrypoint connects to the MQTT broker via
`parking.common`, assembles the [`Component`](../parking/common/component.py)s it owns,
and runs them through the uniform `start()` / `stop()` lifecycle.

- `pi_node.py`     - Raspberry Pi: actuator drivers + reactive gate control, plus the
  sensors. Sensors default to the hardware-free `SimulatedSensors` (which plays a short
  scripted scenario); `PARKING_SENSORS=hardware` selects the Grove/RC522 driver
  skeletons, which remain inert until their `TODO` hardware loops are implemented.
- `laptop_node.py` - Laptop: the state store (kept current by `StorageService`) and the
  parking-lot view. Extend with the planner pipeline as it lands.
- `planner.py`     - Standalone planner service (either node): wires problems to the
  planner and publishes its result. The current planner is a skeleton that returns an
  empty placeholder plan; the service is otherwise idle until a problem is published.
