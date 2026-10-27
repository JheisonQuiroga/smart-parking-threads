"""Messages exchanged between layers (UI) and processes (telemetry).

Every class here must stay immutable and picklable, because instances travel
through ``queue.Queue`` (threads) and ``multiprocessing.Queue`` (processes).
"""

from dataclasses import dataclass
from typing import Optional, Union

from src.models.vehicle import VehicleState

VEHICLE_EVENT_CSV_FIELDS: tuple[str, ...] = (
    "timestamp",
    "vehicle_id",
    "state",
    "slot",
    "occupied",
    "capacity",
)
"""Column names used when persisting :class:`VehicleEvent` rows to CSV."""


@dataclass(frozen=True)
class VehicleEvent:
    """State transition of a vehicle, shared by the UI and the telemetry worker.

    Attributes:
        timestamp: Epoch seconds (``time.time()``) when the transition happened.
        vehicle_id: Identifier of the vehicle that changed state.
        state: New lifecycle state.
        slot: Slot involved in the transition, or ``None``.
        occupied: Occupied slots right after the transition.
        capacity: Total parking capacity.

    Raises:
        TypeError: If ``state`` is not a :class:`VehicleState` instance.
        ValueError: If any numeric field or invariant is out of range.
    """

    timestamp: float
    vehicle_id: int
    state: VehicleState
    slot: Optional[int] = None
    occupied: int = 0
    capacity: int = 0

    def __post_init__(self) -> None:
        """Validate event fields and capacity invariants."""
        if not isinstance(self.state, VehicleState):
            raise TypeError("state must be a VehicleState instance")
        if self.timestamp < 0:
            raise ValueError("timestamp must be >= 0")
        if self.vehicle_id < 1:
            raise ValueError("vehicle_id must be >= 1")
        if self.capacity < 0:
            raise ValueError("capacity must be >= 0")
        if self.occupied < 0:
            raise ValueError("occupied must be >= 0")
        if self.capacity > 0 and self.occupied > self.capacity:
            raise ValueError("occupied cannot exceed capacity")
        if self.slot is not None:
            if self.slot < 0:
                raise ValueError("slot must be >= 0 or None")
            if self.capacity > 0 and self.slot >= self.capacity:
                raise ValueError("slot must be < capacity")

    def to_csv_row(self) -> tuple[float, int, str, Union[int, str], int, int]:
        """Return a flat tuple ready to be written by ``csv.writer``."""
        slot_cell: Union[int, str] = "" if self.slot is None else self.slot
        return (
            self.timestamp,
            self.vehicle_id,
            self.state.value,
            slot_cell,
            self.occupied,
            self.capacity,
        )


@dataclass(frozen=True)
class StopSignal:
    """Sentinel that tells the telemetry worker to finish gracefully."""


TelemetryMessage = Union[VehicleEvent, StopSignal]
"""Type of messages sent through the telemetry ``multiprocessing.Queue``."""
