# config - runtime configuration

Per-node settings consumed at startup (MQTT broker host/port, topic prefixes, parking
layout, simulation parameters). Keep machine-specific values here, out of the code.
Suggested: `pi.yaml`, `laptop.yaml` (commit `.example` versions, keep real ones local).

**`broker.host` is the single switch** for where the broker lives: both nodes read it to
find the [Mosquitto broker](../deploy/mqtt/README.md), so moving the broker between the
laptop and the Pi is a one-line config change. Static address for now; mDNS deferred.
