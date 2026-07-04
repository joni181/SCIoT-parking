# storage  [laptop]

Persistent system state: the vehicle-to-parking-spot mapping and the customer DB
(customer-vehicle association, estimated parking duration, ...). Read by problem
generation and visualization, updated from sensor events.

**Interface:** [`StateStore`](base.py) (= `OccupancyStore` + `CustomerStore`). Default
implementation [`InMemoryStore`](memory_store.py); `OccupancyTracker` in
[`../simulation/`](../simulation/README.md) implements the `OccupancyStore` slice.
