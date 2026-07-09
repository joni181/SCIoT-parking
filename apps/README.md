# apps - runnable entrypoints

Composition roots that connect components to the MQTT broker and manage their
`start()` / `stop()` lifecycle.

- `pi_node.py` - Raspberry Pi: sensors, servo/LED/vehicle actuators, plan
  dispatching, and reactive gate closure. Simulated sensors remain the default.
- `laptop_node.py` - Laptop: state storage, problem generation, forward-search
  planning, and the local operator dashboard. State events trigger replanning;
  the dashboard opens at the configured host/port (default `127.0.0.1:8050`).
  It can run without a Pi connected, but it still needs the MQTT broker process.
- `planner.py` - Optional standalone planner service when planning is deployed
  separately from `laptop_node.py`.
