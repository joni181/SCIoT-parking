# examples

Runnable, hardware-free demonstrations:

- `laptop_dashboard_demo.py` — complete operator dashboard, private real MQTT
  broker, real laptop planning/storage stack, and a guided simulated Pi. This is
  the recommended desktop demonstration. Every simulated human or sensor action
  waits for the **Advance simulation** button, so each instruction remains on
  screen until the operator is ready. Buffers are short-lived resources: B1 is
  reserved while a car enters or is retrieved, then becomes free again while the
  customer is shopping.
- `message_flow_demo.py` — minimal synchronous `MemoryBus` walkthrough for
  understanding the communication contract; no broker or browser.

Install `requirements/laptop.txt`, then run either file directly from the
repository root.

The normal `apps/laptop_node.py` deployment shows the same operator dashboard
without the simulation panel. It listens to the configured live broker and
changes only in response to real Pi traffic (or any separate simulated Pi
client connected to that broker).
