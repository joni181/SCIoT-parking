"""Guided, hardware-free scenarios running through the real MQTT stack."""
from __future__ import annotations

import threading
import time
from itertools import count
from typing import Callable, TypeVar

from ..common import models as m
from ..common.messaging import MqttBus
from ..dispatching import GateSafetyController, PlanDispatcher
from ..planning import ForwardSearchPlanner, PlannerService
from ..problem_generation import PddlProblemGenerator, ProblemGenerationService
from ..storage import InMemoryStore, StorageService
from ..visualization import (
    DashboardModel,
    DashboardSnapshot,
    DemoStatus,
    ScenarioOption,
)
from .devices import RecordingActuators, SimulatedSensors

T = TypeVar("T", bound=m.Message)
_RUNTIME_IDS = count(1)


class ScenarioCancelled(RuntimeError):
    pass


class MessageInbox:
    """Thread-safe command history used by scenario scripts."""

    def __init__(self, bus: MqttBus) -> None:
        self._condition = threading.Condition()
        self._messages: list[m.Message] = []
        for message_type in (
            m.AdmissionResult,
            m.ParkingAssignmentCommand,
            m.VehicleMoveCommand,
            m.GateCommand,
            m.ExitAuthorizationCommand,
        ):
            bus.subscribe_message(message_type.TOPIC, self._append)

    def _append(self, message: m.Message) -> None:
        with self._condition:
            self._messages.append(message)
            self._condition.notify_all()

    def wait_for(
        self,
        message_type: type[T],
        predicate: Callable[[T], bool],
        cancel: threading.Event,
        runnable: threading.Event,
        timeout: float = 8.0,
    ) -> T:
        deadline = time.monotonic() + timeout
        with self._condition:
            while True:
                if cancel.is_set():
                    raise ScenarioCancelled("Scenario reset")
                if not runnable.is_set():
                    self._condition.release()
                    runnable.wait(0.1)
                    self._condition.acquire()
                    deadline += 0.1
                    continue
                for index, message in enumerate(self._messages):
                    if isinstance(message, message_type) and predicate(message):
                        return self._messages.pop(index)  # type: ignore[return-value]
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"Timed out waiting for {message_type.__name__}")
                self._condition.wait(min(remaining, 0.2))


class MqttDemoSystem:
    """One real laptop client and one simulated-Pi client on a broker."""

    def __init__(
        self,
        host: str,
        port: int,
        parking_spots: tuple[str, ...] = ("P1", "P2", "P3"),
        buffer_spots: tuple[str, ...] = ("B1",),
    ) -> None:
        runtime_id = next(_RUNTIME_IDS)
        self.parking_spots = parking_spots
        self.buffer_spots = buffer_spots
        self.laptop_bus = MqttBus(host, port, client_id=f"demo-laptop-{runtime_id}")
        self.pi_bus = MqttBus(host, port, client_id=f"demo-pi-{runtime_id}")
        self.store = InMemoryStore()
        self.model = DashboardModel(self.laptop_bus, self.store, parking_spots, buffer_spots)
        self.sensors = SimulatedSensors(self.pi_bus, source="demo/pi/sensors")
        self.actuators = RecordingActuators(self.pi_bus)
        self.inbox = MessageInbox(self.pi_bus)
        self._laptop_components = [
            StorageService(self.laptop_bus, self.store),
            PlannerService(self.laptop_bus, ForwardSearchPlanner()),
            ProblemGenerationService(
                self.laptop_bus,
                self.store,
                PddlProblemGenerator(spots=parking_spots, buffers=buffer_spots),
            ),
            self.model,
        ]
        self._pi_components = [
            PlanDispatcher(self.pi_bus),
            GateSafetyController(self.pi_bus),
        ]

    def start(self, timeout: float = 6.0) -> None:
        for component in (*self._laptop_components, *self._pi_components):
            component.start()
        self.laptop_bus.start()
        self.pi_bus.start()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.laptop_bus.is_connected() and self.pi_bus.is_connected():
                time.sleep(0.25)  # allow broker subscriptions to settle
                return
            time.sleep(0.05)
        self.stop()
        raise RuntimeError("Demo MQTT clients could not connect to the local broker")

    def stop(self) -> None:
        for component in reversed((*self._laptop_components, *self._pi_components)):
            component.stop()
        for bus in (self.pi_bus, self.laptop_bus):
            try:
                bus.stop()
            except Exception:
                pass


class SwappableDashboardSource:
    """Keep the web server stable while reset replaces the demo runtime."""

    def __init__(self, model: DashboardModel) -> None:
        self._model = model
        self._lock = threading.RLock()

    def replace(self, model: DashboardModel) -> None:
        with self._lock:
            self._model = model

    def start(self) -> None: ...
    def stop(self) -> None: ...

    def render(self) -> None:
        with self._lock:
            self._model.render()

    def snapshot(self) -> DashboardSnapshot:
        with self._lock:
            model = self._model
        return model.snapshot()


class GuidedScenarioController:
    """Dashboard-facing start/advance/reset controller for the three demos."""

    OPTIONS = (
        ScenarioOption("lifecycle", "1 · Complete short-stay lifecycle"),
        ScenarioOption("contention", "2 · Two-car buffer contention"),
        ScenarioOption("full_lot", "3 · Full-lot rejection"),
    )
    TOTAL_STEPS = {"lifecycle": 6, "contention": 12, "full_lot": 3}

    def __init__(
        self,
        system_factory: Callable[[], MqttDemoSystem],
    ) -> None:
        self._factory = system_factory
        self._lock = threading.RLock()
        self._cancel = threading.Event()
        self._runnable = threading.Event()
        self._runnable.set()
        self._advance = threading.Event()
        self._thread: threading.Thread | None = None
        self._status = DemoStatus()
        self._system = self._new_system()
        self.source = SwappableDashboardSource(self._system.model)

    def scenarios(self) -> tuple[ScenarioOption, ...]:
        return self.OPTIONS

    def status(self) -> DemoStatus:
        with self._lock:
            return self._status

    def start_scenario(self, scenario_id: str) -> None:
        if scenario_id not in self.TOTAL_STEPS:
            raise ValueError(f"Unknown scenario: {scenario_id}")
        with self._lock:
            if self._thread and self._thread.is_alive():
                raise RuntimeError("A scenario is already running")
        self._replace_system()
        self._cancel.clear()
        self._runnable.set()
        self._advance.clear()
        with self._lock:
            self._status = DemoStatus(
                state="running",
                scenario_id=scenario_id,
                message="Starting scenario",
                total_steps=self.TOTAL_STEPS[scenario_id],
            )
            self._thread = threading.Thread(
                target=self._run,
                args=(scenario_id,),
                name=f"parking-scenario-{scenario_id}",
                daemon=True,
            )
            self._thread.start()

    def advance(self) -> None:
        with self._lock:
            if not self._thread or not self._thread.is_alive():
                return
            if self._status.state == "waiting_for_advance":
                self._advance.set()

    def reset(self) -> None:
        self._cancel_active()
        self._replace_system()
        with self._lock:
            self._status = DemoStatus(message="Runtime reset; choose a scenario")

    def close(self) -> None:
        self._cancel_active()
        self._system.stop()

    def _new_system(self) -> MqttDemoSystem:
        system = self._factory()
        system.start()
        return system

    def _replace_system(self) -> None:
        self._cancel_active()
        old = self._system
        old.stop()
        new = self._new_system()
        self._system = new
        if hasattr(self, "source"):
            self.source.replace(new.model)

    def _cancel_active(self) -> None:
        self._cancel.set()
        self._runnable.set()
        self._advance.set()
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=3.0)
        self._thread = None

    def _run(self, scenario_id: str) -> None:
        try:
            getattr(self, f"_scenario_{scenario_id}")()
        except ScenarioCancelled:
            return
        except Exception as exc:
            with self._lock:
                current = self._status
                self._status = DemoStatus(
                    state="failed", scenario_id=scenario_id, message="Scenario failed",
                    step=current.step, total_steps=current.total_steps, error=str(exc),
                )
        else:
            with self._lock:
                current = self._status
                self._status = DemoStatus(
                    state="completed", scenario_id=scenario_id, message="Scenario completed",
                    step=current.total_steps, total_steps=current.total_steps,
                )

    def _step(self, message: str) -> None:
        self._check()
        self._advance.clear()
        with self._lock:
            current = self._status
            self._status = DemoStatus(
                state="waiting_for_advance", scenario_id=current.scenario_id, message=message,
                step=current.step + 1, total_steps=current.total_steps,
            )
        while not self._advance.wait(0.1):
            self._check()
        self._check()
        with self._lock:
            current = self._status
            self._status = DemoStatus(
                state="running", scenario_id=current.scenario_id,
                message="Applying simulated sensor events...",
                step=current.step, total_steps=current.total_steps,
            )

    def _check(self) -> None:
        if self._cancel.is_set():
            raise ScenarioCancelled("Scenario reset")
        while not self._runnable.wait(0.1):
            if self._cancel.is_set():
                raise ScenarioCancelled("Scenario reset")

    def _wait(self, message_type: type[T], predicate: Callable[[T], bool]) -> T:
        return self._system.inbox.wait_for(
            message_type, predicate, self._cancel, self._runnable
        )

    def _wait_for_customer_status(self, uid: str, status: str, timeout: float = 8.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._check()
            customer = self._system.store.customer_for(uid)
            if customer is not None and customer.status == status:
                return
            time.sleep(0.05)
        raise TimeoutError(f"Timed out waiting for {uid} to become {status}")

    def _admit(self, uid: str, minutes: int) -> m.ParkingAssignmentCommand:
        sensors = self._system.sensors
        sensors.turn_dial(minutes)
        sensors.car_arrives_at_gate()
        sensors.scan_nfc(uid)
        result = self._wait(m.AdmissionResult, lambda x: x.vehicle_uid == uid)
        if not result.accepted:
            raise RuntimeError(f"{uid} was unexpectedly rejected: {result.reason}")
        assignment = self._wait(m.ParkingAssignmentCommand, lambda x: x.vehicle_uid == uid)
        self._wait(m.GateCommand, lambda x: x.action == m.GATE_OPEN)
        return assignment

    def _depart(self, uid: str, buffer_id: str) -> None:
        sensors = self._system.sensors
        sensors.car_arrives_at_gate()
        sensors.car_leaves(buffer_id)
        sensors.gate_clear()
        self._wait(m.GateCommand, lambda x: x.action == m.GATE_CLOSE)
        self._wait_for_customer_status(uid, "departed")

    def _scenario_lifecycle(self) -> None:
        self._step("Simulate CAR-A arriving, selecting 25 minutes, and scanning at the gate")
        assignment = self._admit("CAR-A", 25)
        self._step(f"Simulate the customer driving into {assignment.buffer_id} and exiting the vehicle")
        self._system.sensors.car_parks(assignment.buffer_id)
        self._system.sensors.gate_clear()
        move = self._wait(m.VehicleMoveCommand, lambda x: x.vehicle_uid == "CAR-A")
        self._step(f"Simulate staff completing the instructed move from {move.from_spot} to {move.to_spot}")
        self._system.sensors.car_leaves(move.from_spot)
        self._system.sensors.car_parks(move.to_spot)
        self._step("CAR-A is parked and the customer is shopping; advance to simulate checkout")
        self._system.sensors.scan_nfc("CAR-A", reader=m.READER_CHECKOUT)
        retrieve = self._wait(m.VehicleMoveCommand, lambda x: x.vehicle_uid == "CAR-A" and x.to_spot == assignment.buffer_id)
        self._step(f"Simulate staff completing the retrieval from {retrieve.from_spot} to {retrieve.to_spot}")
        self._system.sensors.car_leaves(retrieve.from_spot)
        self._system.sensors.car_parks(retrieve.to_spot)
        self._wait(m.ExitAuthorizationCommand, lambda x: x.vehicle_uid == "CAR-A")
        self._wait(m.GateCommand, lambda x: x.action == m.GATE_OPEN)
        self._step("Simulate the customer collecting CAR-A from B1 and leaving")
        self._depart("CAR-A", assignment.buffer_id)

    def _scenario_contention(self) -> None:
        sensors = self._system.sensors
        self._step("Simulate CAR-A arriving and requesting a short stay")
        a = self._admit("CAR-A", 20)
        self._step(f"Simulate the customer driving CAR-A into {a.buffer_id}")
        sensors.car_parks(a.buffer_id)
        sensors.gate_clear()
        move_a = self._wait(m.VehicleMoveCommand, lambda x: x.vehicle_uid == "CAR-A" and x.to_spot == a.spot_id)
        self._step(f"Simulate staff moving CAR-A from {move_a.from_spot} to {move_a.to_spot}")
        sensors.car_leaves(move_a.from_spot)
        sensors.car_parks(move_a.to_spot)
        self._step("CAR-A is parked and shopping; advance to simulate CAR-B arriving")
        b = self._admit("CAR-B", 90)
        self._step(f"Simulate the customer driving CAR-B into {b.buffer_id}")
        sensors.car_parks(b.buffer_id)
        sensors.gate_clear()
        move_b_to_spot = self._wait(m.VehicleMoveCommand, lambda x: x.vehicle_uid == "CAR-B" and x.to_spot == b.spot_id)
        self._step(f"Simulate staff moving CAR-B from {move_b_to_spot.from_spot} to {move_b_to_spot.to_spot}")
        sensors.car_leaves(move_b_to_spot.from_spot)
        sensors.car_parks(move_b_to_spot.to_spot)
        self._step("Simulate CAR-A checking out")
        sensors.scan_nfc("CAR-A", reader=m.READER_CHECKOUT)
        retrieve_a = self._wait(m.VehicleMoveCommand, lambda x: x.vehicle_uid == "CAR-A" and x.to_spot == a.buffer_id)
        self._step(f"Simulate staff retrieving CAR-A from {retrieve_a.from_spot} to {retrieve_a.to_spot}")
        sensors.car_leaves(retrieve_a.from_spot)
        sensors.car_parks(retrieve_a.to_spot)
        self._wait(m.ExitAuthorizationCommand, lambda x: x.vehicle_uid == "CAR-A")
        self._wait(m.GateCommand, lambda x: x.action == m.GATE_OPEN)
        self._step("Simulate CAR-B checking out while CAR-A still occupies the shared buffer")
        sensors.scan_nfc("CAR-B", reader=m.READER_CHECKOUT)
        self._step("Simulate CAR-A being collected and leaving, which releases the buffer")
        self._depart("CAR-A", a.buffer_id)
        move_b = self._wait(m.VehicleMoveCommand, lambda x: x.vehicle_uid == "CAR-B" and x.to_spot == b.buffer_id)
        self._step(f"Simulate staff completing queued retrieval from {move_b.from_spot} to {move_b.to_spot}")
        sensors.car_leaves(move_b.from_spot)
        sensors.car_parks(move_b.to_spot)
        self._wait(m.ExitAuthorizationCommand, lambda x: x.vehicle_uid == "CAR-B")
        self._wait(m.GateCommand, lambda x: x.action == m.GATE_OPEN)
        self._step("Simulate CAR-B being collected and leaving")
        self._depart("CAR-B", b.buffer_id)

    def _scenario_full_lot(self) -> None:
        self._step("Every configured parking spot becomes occupied")
        for spot in self._system.parking_spots:
            self._system.sensors.car_parks(spot)
        self._step("CAR-C requests admission")
        sensors = self._system.sensors
        sensors.turn_dial(30)
        sensors.car_arrives_at_gate()
        sensors.scan_nfc("CAR-C")
        result = self._wait(m.AdmissionResult, lambda x: x.vehicle_uid == "CAR-C")
        if result.accepted:
            raise RuntimeError("Full-lot request was unexpectedly accepted")
        self._step("Planner rejects the request and the gate remains closed")
