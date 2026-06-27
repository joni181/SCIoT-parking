# apps - runnable entrypoints

Composition roots that wire modules into the actual processes you launch. This is the
only place deployment is decided. Each entrypoint connects to the MQTT broker via
`parking.common`, assembles the [`Component`](../parking/common/component.py)s it owns,
and runs them through the uniform `start()` / `stop()` lifecycle.

- `pi_node.py`     - Raspberry Pi: actuator drivers + reactive gate control, plus the
  sensors. Sensors default to the hardware-free `SimulatedSensors` (which plays a short
  scripted scenario); set `PARKING_SENSORS=hardware` to start the real Grove/RC522
  drivers instead.
- `laptop_node.py` - Laptop: the state store (kept current by `StorageService`) and the
  parking-lot view. Extend with the planner pipeline as it lands.
- `planner.py`     - Standalone planner service (either node): solves problems into
  plans. Wired and ready; idle until `problem_generation` publishes problems.
