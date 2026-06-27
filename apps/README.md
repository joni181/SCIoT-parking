# apps - runnable entrypoints

Composition roots that wire modules into the actual processes you launch. This is the
only place deployment is decided.

- `pi_node.py`     - Raspberry Pi: sensors + actuators + dispatching.
- `laptop_node.py` - Laptop: problem generation + planner + storage + visualization.
- `planner.py`     - optional standalone planner service (runs on either node).

Each entrypoint connects to the MQTT broker via `parking.common` and starts the
modules it owns.
