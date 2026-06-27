"""The component lifecycle - the one shape every bus-attached part shares.

A node (Pi or laptop) is, in the end, just a bag of these: sensors that
publish, actuators that consume, controllers that do both. They all attach to a
`MessageBus` and then live for the duration of the process. `Component`
captures *only* that lifetime:

  * `start()` - begin operating (open a device, spin up a poll loop, subscribe).
  * `stop()`  - shut down and release whatever was held.

That is enough for an entrypoint in `apps/` to wire up a list of mixed
components and run them uniformly, without knowing what any one of them is.

It is a `Protocol`, so *anything* with `start()`/`stop()` already satisfies it -
nothing has to inherit. Subscribe-only components (which do all their wiring in
`__init__`) just give `start`/`stop` empty bodies, exactly like the base
`MessageBus` does.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Component(Protocol):
    """Anything that attaches to the bus and runs for the node's lifetime."""

    def start(self) -> None:
        """Begin operating: open devices, start poll loops, subscribe. May no-op."""
        ...

    def stop(self) -> None:
        """Stop and release any resources held. May no-op."""
        ...
