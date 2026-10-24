"""Snapshot de métricas de planificación del SO (enviado del proceso secundario a la GUI)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricsSnapshot:
    """Métricas calculadas por el proceso de telemetría."""

    avg_wait_time: float = 0.0
    avg_service_time: float = 0.0
    avg_turnaround_time: float = 0.0
    utilization_pct: float = 0.0
    throughput_per_min: float = 0.0
    served: int = 0
    waiting: int = 0
