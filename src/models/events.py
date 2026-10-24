"""Eventos que cruzan capas (UI) y procesos (telemetría). Deben ser picklables."""

from dataclasses import dataclass
from typing import Optional

from src.models.vehicle import VehicleState


@dataclass(frozen=True)
class UIEvent:
    """Mensaje de hilos de vehículos hacia la GUI (vía queue.Queue)."""

    timestamp: float
    vehicle_id: int
    state: VehicleState
    slot: Optional[int] = None
    occupied: int = 0
    capacity: int = 0
    message: str = ""


@dataclass(frozen=True)
class TelemetryEvent:
    """Evento crudo de un vehículo hacia el proceso de telemetría (vía mp.Queue)."""

    timestamp: float
    vehicle_id: int
    state: VehicleState
    slot: Optional[int] = None
    occupied: int = 0
    capacity: int = 0
