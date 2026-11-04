"""Vehicle thread simulating an independent OS process competing for resources.

Each vehicle runs as an independent :class:`threading.Thread` with a lifecycle
analogous to OS process states:
1. ``ARRIVING`` (New): waits a random initial delay before requesting resources.
2. ``WAITING`` (Ready / Blocked): attempts to acquire a parking slot via the semaphore.
3. ``PARKED`` (Running): holds a slot (critical resource) for a simulated duration.
4. ``EXITED`` (Terminated): releases the slot and exits.
"""

import random
import threading
import time
from typing import Optional

from src.config import SimulationConfig
from src.core.parking_manager import ParkingManager
from src.core.ports import EventPublisher
from src.models.events import VehicleEvent
from src.models.vehicle import VehicleState


class VehicleThread(threading.Thread):
    """Independent thread modeling a vehicle competing for a parking slot.

    Attributes:
        vehicle_id: Unique positive identifier for this vehicle.
    """

    def __init__(
        self,
        vehicle_id: int,
        parking: ParkingManager,
        publisher: EventPublisher,
        config: SimulationConfig,
        stop_event: threading.Event,
        rng: Optional[random.Random] = None,
    ) -> None:
        """Initialize the vehicle thread.

        Args:
            vehicle_id: Positive integer identifying the vehicle.
            parking: The shared :class:`ParkingManager` instance.
            publisher: Port through which state transitions are published.
            config: Simulation configuration containing time ranges and timeouts.
            stop_event: Synchronization event signaling thread termination.
            rng: Optional dedicated random generator for determinism.

        Raises:
            ValueError: If vehicle_id < 1.
        """
        super().__init__(name=f"VehicleThread-{vehicle_id}", daemon=True)
        if vehicle_id < 1:
            raise ValueError("vehicle_id must be >= 1")

        self._vehicle_id: int = vehicle_id
        self._parking: ParkingManager = parking
        self._publisher: EventPublisher = publisher
        self._config: SimulationConfig = config
        self._stop_event: threading.Event = stop_event

        if rng is not None:
            self._rng: random.Random = rng
        elif config.seed is not None:
            self._rng = random.Random(config.seed + vehicle_id)
        else:
            self._rng = random.Random()

        self._state: VehicleState = VehicleState.ARRIVING
        self._slot: Optional[int] = None

        # Timing tracking
        self._time_arrived: float = 0.0
        self._time_waiting_start: float = 0.0
        self._time_parked_start: float = 0.0
        self._time_exited: float = 0.0
        self._waiting_time_s: float = 0.0
        self._parking_time_s: float = 0.0

    @property
    def vehicle_id(self) -> int:
        """Unique positive identifier of the vehicle."""
        return self._vehicle_id

    @property
    def state(self) -> VehicleState:
        """Current lifecycle state."""
        return self._state

    @property
    def slot(self) -> Optional[int]:
        """Currently assigned parking slot, or None if not parked."""
        return self._slot

    @property
    def waiting_time_s(self) -> float:
        """Accumulated time spent waiting for a slot in seconds."""
        if self._state == VehicleState.WAITING and self._time_waiting_start > 0:
            return time.time() - self._time_waiting_start
        return self._waiting_time_s

    @property
    def parking_time_s(self) -> float:
        """Accumulated time spent parked in seconds."""
        if self._state == VehicleState.PARKED and self._time_parked_start > 0:
            return time.time() - self._time_parked_start
        return self._parking_time_s

    @property
    def turnaround_time_s(self) -> float:
        """Total time elapsed from arrival until exit in seconds."""
        if self._time_arrived == 0.0:
            return 0.0
        end_time = self._time_exited if self._time_exited > 0.0 else time.time()
        return max(0.0, end_time - self._time_arrived)

    def run(self) -> None:
        """Execute the full lifecycle of the vehicle thread."""
        self._time_arrived = time.time()
        arrival_delay = self._rng.uniform(*self._config.arrival_time_range)
        parking_duration = self._rng.uniform(*self._config.parking_time_range)

        # 1. ARRIVING state
        self._emit(VehicleState.ARRIVING)
        if self._stop_event.wait(arrival_delay):
            self._record_exit()
            self._emit(VehicleState.EXITED)
            return

        # 2. WAITING state (entered queue for the shared resource)
        self._time_waiting_start = time.time()
        self._emit(VehicleState.WAITING)

        slot: Optional[int] = None
        while not self._stop_event.is_set():
            slot = self._parking.try_acquire_slot(self._vehicle_id)
            if slot is not None:
                break

        self._waiting_time_s = time.time() - self._time_waiting_start

        # 3. PARKED state & 4. EXITED state
        if slot is not None:
            self._slot = slot
            self._time_parked_start = time.time()
            try:
                self._emit(VehicleState.PARKED, slot=slot)
                if not self._stop_event.is_set():
                    self._stop_event.wait(parking_duration)
            finally:
                self._parking_time_s = time.time() - self._time_parked_start
                self._parking.release_slot(slot=slot, vehicle_id=self._vehicle_id)
                self._slot = None
                self._record_exit()
                self._emit(VehicleState.EXITED, slot=slot)
        else:
            # Cancelled while blocked in queue before acquiring a slot
            self._record_exit()
            self._emit(VehicleState.EXITED)

    def _record_exit(self) -> None:
        """Record the exit timestamp."""
        self._time_exited = time.time()

    def _emit(self, next_state: VehicleState, slot: Optional[int] = None) -> None:
        """Validate transition, update state, and publish the event.

        Args:
            next_state: The new lifecycle state of this vehicle.
            slot: The assigned slot index if parked or leaving, else ``None``.
        """
        # Validate state transition
        if next_state != self._state and not self._state.can_transition_to(next_state):
            raise RuntimeError(
                f"Invalid vehicle state transition from {self._state.name} to {next_state.name}"
            )

        self._state = next_state
        event = VehicleEvent(
            timestamp=time.time(),
            vehicle_id=self._vehicle_id,
            state=next_state,
            slot=slot,
            occupied=self._parking.occupied,
            capacity=self._parking.capacity,
            waiting_time_s=self.waiting_time_s,
            parking_time_s=self.parking_time_s,
        )
        try:
            self._publisher.publish(event)
        except Exception:
            # Defensive programming: publisher failures must not crash the thread
            # or prevent the finally block from releasing slots.
            pass
