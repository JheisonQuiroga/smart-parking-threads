"""Modelo del vehículo y sus estados (analogía con estados de un proceso del SO)."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class VehicleState(Enum):
    """Estados del ciclo de vida de un vehículo."""

    LLEGANDO = "Llegando"                    # Nuevo
    ESPERANDO = "Esperando cupo (Bloqueado)"  # Listo / Bloqueado
    ESTACIONADO = "Estacionado"              # En ejecución (sección crítica)
    SALIO = "Salió"                          # Terminado


@dataclass
class Vehicle:
    """Datos de un vehículo (picklable)."""

    id: int
    state: VehicleState = VehicleState.LLEGANDO
    slot: Optional[int] = None
    wait_time: float = 0.0
    park_time: float = 0.0
