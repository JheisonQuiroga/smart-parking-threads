"""Snapshot of OS scheduling metrics produced by the telemetry process."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricsSnapshot:
    """OS scheduling metrics computed by the telemetry process.

    Attributes:
        average_waiting_time_s: Mean time vehicles spent blocked on the semaphore.
        average_service_time_s: Mean time vehicles stayed parked.
        average_turnaround_time_s: Mean time from arrival to exit.
        utilization_percent: Share of slot-time in use, from 0 to 100.
        throughput_per_minute: Vehicles that exited per minute.
        served_vehicles: Vehicles that completed their lifecycle.
        waiting_vehicles: Vehicles currently blocked waiting for a slot.

    Raises:
        ValueError: If any metric is negative or ``utilization_percent`` is
            outside ``[0.0, 100.0]``.
    """

    average_waiting_time_s: float = 0.0
    average_service_time_s: float = 0.0
    average_turnaround_time_s: float = 0.0
    utilization_percent: float = 0.0
    throughput_per_minute: float = 0.0
    served_vehicles: int = 0
    waiting_vehicles: int = 0

    def __post_init__(self) -> None:
        """Validate that all metrics stay within their mathematical domain."""
        if self.average_waiting_time_s < 0:
            raise ValueError("average_waiting_time_s must be >= 0")
        if self.average_service_time_s < 0:
            raise ValueError("average_service_time_s must be >= 0")
        if self.average_turnaround_time_s < 0:
            raise ValueError("average_turnaround_time_s must be >= 0")
        if not 0.0 <= self.utilization_percent <= 100.0:
            raise ValueError("utilization_percent must be between 0 and 100")
        if self.throughput_per_minute < 0:
            raise ValueError("throughput_per_minute must be >= 0")
        if self.served_vehicles < 0:
            raise ValueError("served_vehicles must be >= 0")
        if self.waiting_vehicles < 0:
            raise ValueError("waiting_vehicles must be >= 0")


EMPTY_METRICS = MetricsSnapshot()
"""Zeroed snapshot used before the telemetry worker emits its first report."""
