"""Messages exchanged between layers (UI) and processes (telemetry).

Every class here must stay immutable and picklable, because instances travel
through ``queue.Queue`` (threads) and ``multiprocessing.Queue`` (processes).
"""

from dataclasses import dataclass
from typing import Optional

from src.models.vehicle import VehicleState


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
    """

    timestamp: float
    vehicle_id: int
    state: VehicleState
    slot: Optional[int] = None
    occupied: int = 0
    capacity: int = 0


@dataclass(frozen=True)
class StopSignal:
    """Sentinel that tells the telemetry worker to finish gracefully."""
