# `parking` package

All application code lives here, one folder per logical module from the architecture
diagram. See [docs/architecture.md](../docs/architecture.md) for the module map and
node placement. Modules communicate only over the pub/sub bus defined in `common/`.

## Folder convention

Each module folder declares its **interface** (the role it plays) and ships a concrete
implementation behind it:

- **`base.py`** — the module's port: a small `typing.Protocol` (e.g. `Sensor`,
  `StateStore`, `Planner`). This is what other code depends on.
- **implementation file(s)** — a class that fulfils the port. Several are still
  *skeletons*: real interface, `TODO`-marked bodies where the hardware/algorithm lands.
- **`__init__.py`** — re-exports the port + implementations so callers write
  `from parking.<module> import <Port>, <Impl>`.

All bus-attached components share the lifecycle interface
[`parking.common.Component`](common/component.py) (`start()` / `stop()`). The
[`simulation/`](simulation/README.md) stand-ins implement these same ports, which is
why they swap cleanly for the real modules. See the **Interfaces** section of
[docs/architecture.md](../docs/architecture.md) for the full port table.
