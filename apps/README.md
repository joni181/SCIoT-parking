# apps - runnable entrypoints

Composition roots that connect components to the MQTT broker and manage their
`start()` / `stop()` lifecycle.

- `pi_node.py` - Raspberry Pi: sensors, actuator drivers, reactive gate control,
  and plan dispatching. Simulated sensors remain the default.
- `laptop_node.py` - Laptop: state storage, problem generation, forward-search
  planning, and parking-lot visualization. State events trigger replanning.
- `planner.py` - Optional standalone planner service when planning is deployed
  separately from `laptop_node.py`.
