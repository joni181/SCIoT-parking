"""Dash-based operator dashboard for the laptop node."""
from __future__ import annotations

import threading
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from .base import View
from .model import DashboardModel, DashboardSnapshot, SpotSnapshot

_LOGO = "/assets/lidl-logo.svg"


@dataclass(frozen=True)
class ScenarioOption:
    scenario_id: str
    label: str


@dataclass(frozen=True)
class DemoStatus:
    state: str = "idle"
    scenario_id: str = ""
    message: str = "Ready"
    step: int = 0
    total_steps: int = 0
    error: str = ""


@runtime_checkable
class DashboardSource(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def render(self) -> None: ...
    def snapshot(self) -> DashboardSnapshot: ...


@runtime_checkable
class DemoController(Protocol):
    def scenarios(self) -> tuple[ScenarioOption, ...]: ...
    def status(self) -> DemoStatus: ...
    def start_scenario(self, scenario_id: str) -> None: ...
    def advance(self) -> None: ...
    def reset(self) -> None: ...


class DashboardView(View):
    """Serve a read-only local operator dashboard in a stoppable thread."""

    def __init__(
        self,
        source: DashboardSource,
        host: str = "127.0.0.1",
        port: int = 8050,
        open_browser: bool = True,
        demo_controller: DemoController | None = None,
    ) -> None:
        self._source = source
        self._host = host
        self._port = port
        self._open_browser = open_browser
        self._demo = demo_controller
        self._app = None
        self._server = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        browser_host = "127.0.0.1" if self._host in ("0.0.0.0", "::") else self._host
        return f"http://{browser_host}:{self._port}"

    @property
    def app(self):
        if self._app is None:
            self._app = create_dashboard_app(self._source, self._demo)
        return self._app

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        try:
            from werkzeug.serving import make_server
        except ImportError as exc:
            raise RuntimeError(
                "Dashboard dependencies are missing. Run: pip install -r requirements/laptop.txt"
            ) from exc

        self._source.start()
        self._server = make_server(self._host, self._port, self.app.server, threaded=True)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="parking-dashboard",
            daemon=True,
        )
        self._thread.start()
        if self._open_browser:
            threading.Timer(0.35, lambda: webbrowser.open(self.url)).start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._source.stop()

    def render(self) -> None:
        self._source.render()


def create_dashboard_app(source: DashboardSource, demo_controller: DemoController | None = None):
    """Build the Dash app separately so it can be exercised with a test client."""
    try:
        from dash import Dash, Input, Output, State, ctx, dcc, html
    except ImportError as exc:
        raise RuntimeError(
            "Dashboard dependencies are missing. Run: pip install -r requirements/laptop.txt"
        ) from exc

    assets = Path(__file__).with_name("assets")
    app = Dash(__name__, assets_folder=str(assets), title="LIDL Parking Control")
    demo_panel = _demo_layout(html, dcc, demo_controller) if demo_controller else None

    def heading(title, tag):
        return html.Div(className="panel-heading", children=[html.H2(title), html.Span(tag)])

    app.layout = html.Div(className="shell", children=[
        dcc.Interval(id="refresh", interval=500, n_intervals=0),
        html.Header(className="topbar", children=[
            html.Div(className="brand", children=[
                html.Img(src=_LOGO, className="brand-logo", alt="LIDL"),
                html.Div([
                    html.P("LIDL · SCIoT · GROUP 04", className="eyebrow"),
                    html.H1("LIDL Parking Control Center"),
                    html.P("Lidl lohnt sich!", className="subtitle"),
                ]),
            ]),
            html.Div(className="health-row", children=[
                html.Span(id="connection-badge"),
            ]),
        ]),
        demo_panel,
        html.Div(id="kpi-row", className="kpi-grid"),
        html.Section(id="operator-instruction", className="instruction-panel"),
        html.Main(className="dashboard-grid", children=[
            html.Section(className="panel lot-panel", children=[
                heading("LIDL parking lot", "Sensor-confirmed"),
                html.Div(id="lot-map"),
            ]),
            html.Section(className="panel assignments-panel", children=[
                heading("Assignments", "All customers"),
                html.Div(id="assignments-table", className="table-wrap"),
            ]),
        ]),
        html.Details(className="diagnostics", children=[
            html.Summary("Technical diagnostics"),
            html.Div(className="diagnostics-grid", children=[
                html.Section(className="panel plan-panel", children=[
                    heading("Latest plan", "Issued actions"),
                    html.Div(id="admission-result"),
                    html.Div(id="plan-view"),
                ]),
                html.Section(className="panel activity-panel", children=[
                    heading("Recent activity", "Newest first"),
                    html.Div(id="activity-feed"),
                ]),
            ]),
        ]),
        html.Footer(className="lidl-footer", children=[
            html.Img(src=_LOGO, alt="LIDL"),
            html.Span("LIDL Parking ↝ Park smart. Lidl lohnt sich!"),
            html.Img(src=_LOGO, alt="LIDL"),
        ]),
    ])

    outputs = [
        Output("connection-badge", "children"), Output("connection-badge", "className"),
        Output("kpi-row", "children"), Output("operator-instruction", "children"),
        Output("operator-instruction", "className"), Output("lot-map", "children"),
        Output("assignments-table", "children"), Output("admission-result", "children"),
        Output("plan-view", "children"), Output("activity-feed", "children"),
    ]
    if demo_controller:
        outputs.extend([
            Output("scenario-status", "children"),
            Output("scenario-progress", "value"),
            Output("advance-scenario", "disabled"),
        ])

    @app.callback(*outputs, Input("refresh", "n_intervals"))
    def refresh(_tick):
        snapshot = source.snapshot()
        result = [
            "● MQTT connected" if snapshot.connected else "○ MQTT offline",
            "badge ok" if snapshot.connected else "badge danger",
            _kpis(html, snapshot),
            _operator_instruction(html, snapshot),
            f"instruction-panel {snapshot.operator_instruction.mode}",
            _lot(html, snapshot),
            _assignments(html, snapshot),
            _admission(html, snapshot),
            _plan(html, snapshot),
            _activity(html, snapshot),
        ]
        if demo_controller:
            status = demo_controller.status()
            maximum = max(status.total_steps, 1)
            progress = min(status.step / maximum * 100, 100)
            message = status.error or status.message
            result.extend([
                html.Div([
                    html.Strong(status.state.replace("_", " ").title()),
                    html.Span(message),
                ], className=f"scenario-copy {status.state}"),
                progress,
                status.state != "waiting_for_advance",
            ])
        return tuple(result)

    if demo_controller:
        @app.callback(
            Output("demo-action-result", "children"),
            Input("start-scenario", "n_clicks"),
            Input("advance-scenario", "n_clicks"),
            Input("reset-scenario", "n_clicks"),
            State("scenario-select", "value"),
            prevent_initial_call=True,
        )
        def demo_action(_start, _advance, _reset, selected):
            try:
                if ctx.triggered_id == "start-scenario":
                    demo_controller.start_scenario(selected)
                elif ctx.triggered_id == "advance-scenario":
                    demo_controller.advance()
                elif ctx.triggered_id == "reset-scenario":
                    demo_controller.reset()
                return ""
            except (RuntimeError, ValueError) as exc:
                return str(exc)

    return app


def _demo_layout(html, dcc, controller: DemoController):
    options = [{"label": item.label, "value": item.scenario_id} for item in controller.scenarios()]
    default = options[0]["value"] if options else None
    return html.Section(className="demo-panel", children=[
        html.Div([
            html.P("LIDL STANDALONE SIMULATION", className="eyebrow"),
            html.Div(id="scenario-status"),
            html.Div(id="demo-action-result", className="form-error"),
        ]),
        html.Div(className="scenario-controls", children=[
            dcc.Dropdown(
                id="scenario-select", options=options, value=default,
                clearable=False, className="scenario-select",
            ),
            html.Button("Start", id="start-scenario", n_clicks=0, className="primary"),
            html.Button("Advance simulation", id="advance-scenario", n_clicks=0, disabled=True),
            html.Button("Reset", id="reset-scenario", n_clicks=0),
        ]),
        html.Progress(id="scenario-progress", value=0, max=100),
    ])


def _kpis(html, snapshot: DashboardSnapshot):
    values = [
        (snapshot.free_count, "Free parking spots", "green"),
        (snapshot.occupied_count, "Occupied locations", "red"),
        (snapshot.active_requests, "Active vehicles", "blue"),
        (len(snapshot.assignments), "Customer records", "violet"),
    ]
    return [html.Div(className=f"kpi {tone}", children=[html.Strong(str(value)), html.Span(label)]) for value, label, tone in values]


def _operator_instruction(html, snapshot: DashboardSnapshot):
    instruction = snapshot.operator_instruction
    route = None
    if instruction.from_spot and instruction.to_spot:
        route = html.Div(className="instruction-route", children=[
            html.Span(instruction.from_spot),
            html.Strong("→"),
            html.Span(instruction.to_spot),
        ])
    confirmations = None
    if instruction.confirmations:
        confirmations = html.Div(className="confirmation-list", children=[
            html.Div(className=f"confirmation {'confirmed' if item.confirmed else 'pending'}", children=[
                html.Strong("✓" if item.confirmed else "○"),
                html.Span(item.label),
            ]) for item in instruction.confirmations
        ])
    labels = {
        "action": "STAFF ACTION REQUIRED",
        "ready": "CUSTOMER ACTION",
        "waiting": "SYSTEM WORKING",
        "error": "ATTENTION REQUIRED",
        "idle": "CURRENT INSTRUCTION",
    }
    return html.Div(className="instruction-content", children=[
        html.Div(className="instruction-copy", children=[
            html.P(labels.get(instruction.mode, "CURRENT INSTRUCTION"), className="eyebrow"),
            html.H2(instruction.title),
            html.P(instruction.detail),
        ]),
        route,
        confirmations,
    ])


def _lot(html, snapshot: DashboardSnapshot):
    gate_open = snapshot.gate_state == "open"
    gate_state = "open" if gate_open else "closed"
    gate_presence = "vehicle-present" if snapshot.gate_present else "approach-clear"
    gate_copy = "Vehicle at gate" if snapshot.gate_present else "Approach clear"

    def cell(spot: SpotSnapshot):
        vehicle = spot.vehicle_uid or spot.assigned_vehicle
        state_label = "Move required" if spot.state == "moving" else spot.state.title()
        secondary = vehicle or ("Available" if spot.state == "free" else state_label)
        return html.Div(className=f"spot {spot.state} {spot.kind}", children=[
            html.Div([html.Strong(spot.spot_id), html.Span(spot.kind.title())]),
            html.P(secondary),
            html.Small(f"● {state_label}"),
        ])
    return html.Div(className="lot-layout", children=[
        html.Div(className=f"gate-card {gate_state} {gate_presence}", children=[
            html.Div(className="gate-arm", children=html.Span()),
            html.Div(className="gate-copy", children=[
                html.Span("ENTRY / EXIT"),
                html.Strong(f"Gate {snapshot.gate_state.title()}"),
                html.Small(gate_copy),
            ]),
        ]),
        html.Div(className="buffer-row", children=[cell(s) for s in snapshot.buffer_spots]),
        html.Div(className="parking-row", children=[cell(s) for s in snapshot.parking_spots]),
        html.Div(className="lot-legend", children=[
            html.Span("● Free", className="free-text"), html.Span("● Occupied", className="occupied-text"),
            html.Span("● Assigned", className="assigned-text"), html.Span("● Move required", className="moving-text"),
        ]),
    ])


def _assignments(html, snapshot: DashboardSnapshot):
    if not snapshot.assignments:
        return html.Div("No customer activity yet", className="empty-state")
    headings = ["Vehicle", "Duration", "Assignment", "Location", "Status"]
    rows = []
    for item in reversed(snapshot.assignments):
        assignment = " / ".join(x for x in (item.assigned_buffer, item.assigned_spot) if x) or "—"
        rows.append(html.Tr([
            html.Td([html.Strong(item.vehicle_uid or "—"), html.Small(item.uid)]),
            html.Td(f"{item.expected_minutes} min" if item.expected_minutes is not None else "—"),
            html.Td(assignment), html.Td(item.current_location or "—"),
            html.Td(html.Span(item.status_label, className=f"status-tag {item.status}")),
        ]))
    return html.Table([html.Thead(html.Tr([html.Th(x) for x in headings])), html.Tbody(rows)])


def _admission(html, snapshot: DashboardSnapshot):
    item = snapshot.latest_admission
    if item.accepted is None:
        return None
    text = f"{item.vehicle_uid} accepted · {item.assigned_spot}" if item.accepted else f"{item.vehicle_uid} rejected · {item.reason}"
    return html.Div(text, className=f"admission {'accepted' if item.accepted else 'rejected'}")


def _plan(html, snapshot: DashboardSnapshot):
    plan = snapshot.latest_plan
    if not plan.problem_id:
        return html.Div("Waiting for a planning request", className="empty-state")
    customer = next((x for x in snapshot.assignments if x.vehicle_uid == plan.vehicle_uid), None)
    progress = customer.status_label if customer else "Awaiting sensor confirmation"
    actions = [html.Li([html.Span(str(a.index)), html.Div([html.Strong(a.name), html.Small(" · ".join(a.args))])]) for a in plan.actions]
    if not actions:
        actions = [html.Li(className="no-action", children="No action required")]
    return html.Div([
        html.Div(className="plan-meta", children=[
            html.Span(plan.problem_id), html.Strong((plan.purpose or "idle").title()),
            html.Span(f"Physical phase: {progress}"),
        ]),
        html.Ol(actions, className="plan-actions"),
    ])


def _activity(html, snapshot: DashboardSnapshot):
    if not snapshot.activity:
        return html.Div("Waiting for MQTT activity", className="empty-state")
    return html.Div(className="activity-list", children=[
        html.Div(className="activity-item", children=[
            html.Span(item.kind[:1].upper(), className=f"activity-icon {item.kind}"),
            html.Div([html.Strong(item.summary), html.Small(item.message_type.replace("_", " "))]),
            html.Time(datetime.fromtimestamp(item.timestamp).strftime("%H:%M:%S")),
        ]) for item in snapshot.activity[:20]
    ])
