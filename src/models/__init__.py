"""[M] Models: pure data contracts. No concurrency, no Tkinter, no I/O."""

from src.models.events import StopSignal, VehicleEvent
from src.models.metrics import MetricsSnapshot
from src.models.vehicle import VehicleInfo, VehicleState

__all__ = [
    "MetricsSnapshot",
    "StopSignal",
    "VehicleEvent",
    "VehicleInfo",
    "VehicleState",
]
