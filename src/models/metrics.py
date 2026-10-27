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
    """

    average_waiting_time_s: float = 0.0
    average_service_time_s: float = 0.0
    average_turnaround_time_s: float = 0.0
    utilization_percent: float = 0.0
    throughput_per_minute: float = 0.0
    served_vehicles: int = 0
    waiting_vehicles: int = 0
