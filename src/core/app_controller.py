"""AppController facade coordinating the simulation, concurrency primitives, and UI events."""

import queue
import threading
from typing import Any, Optional

from src.config import DEFAULT_CONFIG, SimulationConfig
from src.core.parking_manager import ParkingManager
from src.core.ports import EventPublisher
from src.core.queue_publisher import QueueEventPublisher
from src.core.vehicle_thread import VehicleThread
from src.models.events import VehicleEvent


class AppController:
    """Facade exposing the complete simulation control API to the presentation layer.

    This class coordinates the lifecycle of the parking lot, manages vehicle threads,
    dispatches events to the UI and telemetry queues, and enforces clean shutdown.
    """

    def __init__(
        self,
        config: SimulationConfig = DEFAULT_CONFIG,
        telemetry_queue: Optional[Any] = None,
        publisher: Optional[EventPublisher] = None,
    ) -> None:
        """Initialize the application controller.

        Args:
            config: Initial simulation configuration.
            telemetry_queue: Optional queue delivering events to the telemetry worker process.
            publisher: Optional custom event publisher (defaults to QueueEventPublisher).
        """
        self._config: SimulationConfig = config
        self._telemetry_queue: Optional[Any] = telemetry_queue
        self._ui_queue: "queue.Queue[VehicleEvent]" = queue.Queue()

        self._publisher: EventPublisher = (
            publisher
            if publisher is not None
            else QueueEventPublisher(
                ui_queue=self._ui_queue,
                telemetry_queue=self._telemetry_queue,
            )
        )

        self._parking: ParkingManager = ParkingManager(
            capacity=config.capacity,
            acquire_timeout_s=config.acquire_timeout_s,
        )

        self._stop_event: threading.Event = threading.Event()
        self._threads: list[VehicleThread] = []
        self._threads_lock: threading.Lock = threading.Lock()
        self._next_vehicle_id: int = 0
        self._is_running: bool = False

    @property
    def config(self) -> SimulationConfig:
        """Current simulation configuration."""
        return self._config

    @property
    def is_running(self) -> bool:
        """Return True if a simulation run is actively in progress."""
        return self._is_running

    @property
    def capacity(self) -> int:
        """Total parking capacity."""
        return self._parking.capacity

    @property
    def occupied(self) -> int:
        """Current number of occupied slots."""
        return self._parking.occupied

    @property
    def available(self) -> int:
        """Current number of free slots."""
        return self._parking.available

    @property
    def ui_queue(self) -> "queue.Queue[VehicleEvent]":
        """The queue containing pending UI update events."""
        return self._ui_queue

    @property
    def active_threads_count(self) -> int:
        """Number of active vehicle threads still alive."""
        with self._threads_lock:
            return sum(1 for t in self._threads if t.is_alive())

    def start(self, config: Optional[SimulationConfig] = None) -> None:
        """Start a new simulation run with the specified or current configuration.

        Args:
            config: Optional override configuration for this run.

        Raises:
            RuntimeError: If a simulation is already running.
        """
        if self._is_running:
            raise RuntimeError("Simulation is already running. Call stop() or reset() first.")

        if config is not None:
            self._config = config

        # A fresh event per run: threads of a previous run keep their own (already
        # set) event, so they can never be revived by this run.
        self._stop_event = threading.Event()
        self._parking = ParkingManager(
            capacity=self._config.capacity,
            acquire_timeout_s=self._config.acquire_timeout_s,
        )

        with self._threads_lock:
            self._threads.clear()
            self._next_vehicle_id = 0
            for _ in range(self._config.initial_vehicles):
                self._next_vehicle_id += 1
                thread = VehicleThread(
                    vehicle_id=self._next_vehicle_id,
                    parking=self._parking,
                    publisher=self._publisher,
                    config=self._config,
                    stop_event=self._stop_event,
                )
                self._threads.append(thread)
                thread.start()

        self._is_running = True

    def add_vehicle(self) -> int:
        """Dynamically spawn and inject a new vehicle thread into the simulation.

        Returns:
            The unique vehicle ID assigned to the new vehicle thread.

        Raises:
            RuntimeError: If called while the simulation is stopped.
        """
        if not self._is_running:
            raise RuntimeError("Cannot add a vehicle to a stopped simulation. Call start() first.")

        with self._threads_lock:
            self._next_vehicle_id += 1
            vehicle_id = self._next_vehicle_id
            thread = VehicleThread(
                vehicle_id=vehicle_id,
                parking=self._parking,
                publisher=self._publisher,
                config=self._config,
                stop_event=self._stop_event,
            )
            self._threads.append(thread)
            thread.start()

        return vehicle_id

    def stop(self, timeout_s: float = 2.0) -> None:
        """Signal all active threads to stop and wait for their termination.

        Args:
            timeout_s: Maximum seconds to wait per thread during join.
        """
        self._stop_event.set()

        # Copy the list under the lock, then join outside it so add_vehicle() and
        # other callers are never blocked while threads finish.
        with self._threads_lock:
            threads_to_join = list(self._threads)

        for thread in threads_to_join:
            if thread.is_alive():
                thread.join(timeout=timeout_s)

        self._is_running = False

    def reset(self) -> None:
        """Stop any active simulation and reset all state for a clean run."""
        if self._is_running:
            self.stop()

        # Drain the UI queue
        while not self._ui_queue.empty():
            try:
                self._ui_queue.get_nowait()
            except queue.Empty:
                break

        with self._threads_lock:
            self._threads.clear()
            self._next_vehicle_id = 0

        # Never clear the previous event: a thread that outlived join() must stay stopped.
        self._stop_event = threading.Event()
        self._parking = ParkingManager(
            capacity=self._config.capacity,
            acquire_timeout_s=self._config.acquire_timeout_s,
        )

    def shutdown(self) -> None:
        """Perform a complete shutdown releasing all resources."""
        self.stop()
        self.reset()

    def drain_ui_events(self) -> list[VehicleEvent]:
        """Retrieve all currently pending UI events non-blockingly.

        Returns:
            A list of :class:`VehicleEvent` instances ready to update widgets.
        """
        events: list[VehicleEvent] = []
        while not self._ui_queue.empty():
            try:
                events.append(self._ui_queue.get_nowait())
            except queue.Empty:
                break
        return events
