# dispatching  [Raspberry Pi]

Consumes solved plans and issues actuator commands in order.

**Interface:** [`Dispatcher`](base.py) (a `Component`).
[`dispatcher.py`](dispatcher.py) maps `park` and `retrieve` steps to vehicle-move
commands. The reactive gate rule remains in
[`../simulation/`](../simulation/README.md).
