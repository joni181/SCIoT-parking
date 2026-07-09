# visualization  [laptop]

Local Dash operator UI that reads the shared `StateStore` and observes the bus
(no coupling to control logic). It shows parking and buffer occupancy,
customer/vehicle assignments, lifecycle progress, MQTT health, the current
human instruction, and its required sensor confirmations. Gate open/closed and
gate-presence sensor state are rendered inside the parking-lot map because they
belong to the physical movement path. Issued plans, admission outcomes, and
recent activity remain available in a collapsed technical-diagnostics section.

**Interface:** [`View`](base.py) (a `Component`). `DashboardView` serves a
stoppable local Flask-backed dashboard; `DashboardModel` provides immutable,
thread-safe snapshots for its 500 ms refresh callback. `ConsoleLotView` remains
available as a dependency-free fallback.

Configuration defaults to `127.0.0.1:8050` and can be changed through
`dashboard_host`, `dashboard_port`, and `dashboard_open_browser` in
`config/config.yaml` or their `PARKING_DASHBOARD_*` environment equivalents.
Keep it bound to loopback unless remote access is intentionally required: this
lab dashboard has no authentication.
