# config - runtime configuration

Machine-specific settings read at startup, kept out of the code.

- `config.example.yaml` — committed template. Copy it to `config.yaml` (which is
  git-ignored, so each machine keeps its own) and edit the values.
- `config.yaml` — your local, real settings. Loaded automatically by
  `parking.common.config.load_settings()`.

**`broker_host` is the single switch** for where the broker lives: every node
reads it to find the [pure-Python broker](../deploy/broker.py), so moving the
broker is a one-line change. Set it to the LAN IP of the machine running the
broker (the laptop). Environment variables (`PARKING_BROKER_HOST`,
`PARKING_BROKER_PORT`) override the file for one-off runs.

Static address for now; mDNS auto-discovery deferred. Per-node files
(`pi.yaml` / `laptop.yaml`) can be added later if node-specific settings appear.

The laptop dashboard has separate local settings: `dashboard_host` (loopback by
default), `dashboard_port` (8050), and `dashboard_open_browser`. Environment
overrides are `PARKING_DASHBOARD_HOST`, `PARKING_DASHBOARD_PORT`, and
`PARKING_DASHBOARD_OPEN_BROWSER` (`0`/`false` disables browser opening).
