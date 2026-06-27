"""Parking-lot and plan visualization (Laptop, Python).

    from parking.visualization import View              # the interface
    from parking.visualization import ConsoleLotView    # skeleton

A `View` is a read-only renderer of system state - it observes the bus / a
`StateStore` and draws, with no path back to control logic.
"""
from .base import View
from .console_view import ConsoleLotView

__all__ = ["View", "ConsoleLotView"]
