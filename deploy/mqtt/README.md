# MQTT broker (Mosquitto)

Broker configuration for the message bus.

**Deployment is flexible (like the planner):** one Mosquitto instance, started on *either*
the laptop or the Pi depending on what we settle on — not a separate host. Switching hosts
should only mean starting Mosquitto on the other machine and updating one config value; no
code changes.

Both nodes locate the broker via a **static address in [`config/`](../../config/README.md)**
(`broker.host` / `broker.port`). Auto-discovery (mDNS / `*.local`) is deferred — revisit only
if reconfiguring IPs becomes annoying.
