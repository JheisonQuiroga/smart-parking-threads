"""Vehicle lifecycle states and the vehicle read model.

Each state maps to a classic OS process state, which is the core analogy of the
simulator: a vehicle (thread) competes for a finite resource (parking slots).
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class VehicleState(Enum):
    """Vehicle lifecycle mapped to OS process states."""

    ARRIVING = "arriving"  # New: the thread exists but has not requested the resource
    WAITING = "waiting"  # Ready / Blocked: waiting on the semaphore
    PARKED = "parked"  # Running: holds the shared resource (a slot)
    EXITED = "exited"  # Terminated: released the resource and finished

    @property
    def is_terminal(self) -> bool:
        """Return ``True`` when the vehicle can no longer change state."""
        return self is VehicleState.EXITED

    @property
    def is_blocked(self) -> bool:
        """Return ``True`` when the vehicle is blocked waiting for a slot."""
        return self is VehicleState.WAITING

    @property
    def is_holding_slot(self) -> bool:
        """Return ``True`` when the vehicle is in the critical resource (parked)."""
        return self is VehicleState.PARKED

    def can_transition_to(self, next_state: "VehicleState") -> bool:
        """Return ``True`` if moving from ``self`` to ``next_state`` is valid.

        Valid transitions follow the OS process lifecycle, including early
        termination (``EXITED``) when a stop signal cancels an arriving or
        waiting thread.
        """
        valid_targets = _VALID_TRANSITIONS[self]
        return next_state in valid_targets


_VALID_TRANSITIONS: dict[VehicleState, frozenset[VehicleState]] = {
    VehicleState.ARRIVING: frozenset({VehicleState.WAITING, VehicleState.EXITED}),
    VehicleState.WAITING: frozenset(
        {VehicleState.WAITING, VehicleState.PARKED, VehicleState.EXITED}
    ),
    VehicleState.PARKED: frozenset({VehicleState.EXITED}),
    VehicleState.EXITED: frozenset(),
}


@dataclass
class VehicleInfo:
    """Read model of a vehicle, as displayed in the UI table.

    Attributes:
        vehicle_id: Unique, positive identifier of the vehicle.
        state: Current lifecycle state.
        slot: Index of the occupied slot, or ``None`` if not parked.
        waiting_time_s: Accumulated time spent waiting for a slot.
        parking_time_s: Accumulated time spent parked.

    Raises:
        TypeError: If ``state`` is not a :class:`VehicleState` instance.
        ValueError: If ``vehicle_id`` is not positive, ``slot`` is negative or a
            time is negative.
    """

    vehicle_id: int
    state: VehicleState = VehicleState.ARRIVING
    slot: Optional[int] = None
    waiting_time_s: float = 0.0
    parking_time_s: float = 0.0

    def __post_init__(self) -> None:
        """Validate identifiers, state type and accumulated times."""
        if not isinstance(self.state, VehicleState):
            raise TypeError("state must be a VehicleState instance")
        if self.vehicle_id < 1:
            raise ValueError("vehicle_id must be >= 1")
        if self.slot is not None and self.slot < 0:
            raise ValueError("slot must be >= 0 or None")
        if self.waiting_time_s < 0 or self.parking_time_s < 0:
            raise ValueError("accumulated times must be >= 0")

    @property
    def turnaround_time_s(self) -> float:
        """Total time spent in the system (waiting + parking)."""
        return self.waiting_time_s + self.parking_time_s
