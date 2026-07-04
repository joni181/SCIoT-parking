# dispatching  [Raspberry Pi]

The control logic that turns a solved plan into action: consumes the planner's output
and issues commands to `actuators` (gate, buffer LED, vehicle moves) in the right order.

**Interface:** [`Dispatcher`](base.py) (a `Component`). Plan executor (skeleton) in
[`dispatcher.py`](dispatcher.py). The reactive gate rule lives for now as
`ReactiveGateController` in [`../simulation/`](../simulation/README.md).
