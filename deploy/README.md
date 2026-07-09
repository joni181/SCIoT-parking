# deploy - broker & run

Operational glue for running the distributed system.

- `broker.py` — the MQTT broker, a pure-Python `amqtt` server (the whole stack
  stays 100% Python). Run it on the laptop: `python deploy/broker.py`. Binds
  `0.0.0.0:1883` so the Pi can reach it across the LAN; override the port with
  `PARKING_BROKER_PORT`.

The node apps in `apps/` connect to the broker via `MqttBus`, reading the
broker host/port from `config/config.yaml`. Full startup steps are in the
[Getting started guide](../README.md).

For a single-command desktop demonstration, `examples/laptop_dashboard_demo.py`
starts this same broker on a free loopback port, connects separate laptop and
simulated-Pi MQTT clients, opens the dashboard, and terminates the private
broker on exit.
