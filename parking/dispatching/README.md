# dispatching  [Raspberry Pi]

Consumes solved plans and issues actuator commands in order.

**Interface:** [`Dispatcher`](base.py) (a `Component`).
[`dispatcher.py`](dispatcher.py) maps admission, indication, parking, retrieval,
and exit steps to commands. [`gate_safety.py`](gate_safety.py) closes the servo
reactively only after a vehicle has been detected and has cleared the gate.
