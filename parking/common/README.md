# common  [both nodes]

The communication layer and shared contracts. Everything here is imported identically
on the Pi and the laptop, so the two nodes always agree on how they talk.

- `messaging/` - MQTT client wrapper (connect / publish / subscribe).
- `models/`    - shared event & command message schemas.
- `config/`    - loading runtime config (broker host, node settings).
- topic catalog - the single source of truth for topic names.
