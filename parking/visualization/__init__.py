"""Parking-lot and plan visualization (Laptop, Python).

    from parking.visualization import View              # the interface
    from parking.visualization import DashboardView     # operator dashboard
    from parking.visualization import ConsoleLotView    # lightweight fallback

A `View` is a read-only renderer of system state - it observes the bus / a
`StateStore` and draws, with no path back to control logic.
"""
from .base import View
from .console_view import ConsoleLotView
from .dashboard_view import (
    DashboardSource,
    DashboardView,
    DemoController,
    DemoStatus,
    ScenarioOption,
    create_dashboard_app,
)
from .model import (
    ActivitySnapshot,
    AdmissionSnapshot,
    AssignmentSnapshot,
    ConfirmationSnapshot,
    DashboardModel,
    DashboardSnapshot,
    OperatorInstructionSnapshot,
    PlanActionSnapshot,
    PlanSnapshot,
    SpotSnapshot,
)

__all__ = [
    "View", "ConsoleLotView", "DashboardView", "DashboardModel", "DashboardSource",
    "DemoController", "DemoStatus", "ScenarioOption", "create_dashboard_app",
    "DashboardSnapshot", "SpotSnapshot", "AssignmentSnapshot", "PlanSnapshot",
    "PlanActionSnapshot", "AdmissionSnapshot", "ActivitySnapshot",
    "ConfirmationSnapshot", "OperatorInstructionSnapshot",
]
