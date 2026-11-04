"""Pure OS-scheduling metrics computed from a stream of vehicle events.

This module has no I/O and no concurrency, so the formulas can be unit-tested
without spawning processes. :class:`TelemetryWorker` feeds it from its queue.

Definitions (per vehicle that reached the parking lot):
    waiting time    = PARKED.timestamp - WAITING.timestamp
    service time    = EXITED.timestamp - PARKED.timestamp
    turnaround time = EXITED.timestamp - WAITING.timestamp   (waiting + service)
    utilization %   = busy slot-seconds / (capacity * elapsed seconds) * 100
    throughput      = served vehicles / elapsed minutes
"""

from dataclasses import dataclass
from typing import Optional

from src.models.events import VehicleEvent
from src.models.metrics import MetricsSnapshot
from src.models.vehicle import VehicleState

_SECONDS_PER_MINUTE = 60.0
_MAX_PERCENT = 100.0


@dataclass
class _VehicleTimeline:
    """Timestamps of the lifecycle transitions of one vehicle."""

    waiting_at: Optional[float] = None
    parked_at: Optional[float] = None
    exited_at: Optional[float] = None


class MetricsCalculator:
    """Accumulates vehicle events and produces :class:`MetricsSnapshot` objects."""

    def __init__(self, capacity: int, start_time: Optional[float] = None) -> None:
        """Create an empty calculator.

        Args:
            capacity: Total parking slots, used for the utilization percentage.
            start_time: Epoch seconds when the run started. If ``None``, the
                timestamp of the first registered event is used.

        Raises:
            ValueError: If ``capacity`` < 1.
        """
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._capacity = capacity
        self._start_time = start_time
        self._timelines: dict[int, _VehicleTimeline] = {}
        self._waiting_times: list[float] = []
        self._service_times: list[float] = []
        self._turnaround_times: list[float] = []
        self._closed_busy_seconds = 0.0

    @property
    def capacity(self) -> int:
        """Total parking slots."""
        return self._capacity

    def register(self, event: VehicleEvent) -> None:
        """Update the accumulated statistics with one state transition."""
        if self._start_time is None:
            self._start_time = event.timestamp

        timeline = self._timelines.setdefault(event.vehicle_id, _VehicleTimeline())
        if event.state is VehicleState.WAITING and timeline.waiting_at is None:
            timeline.waiting_at = event.timestamp
        elif event.state is VehicleState.PARKED:
            self._register_parked(timeline, event.timestamp)
        elif event.state is VehicleState.EXITED:
            self._register_exited(timeline, event.timestamp)

    def snapshot(self, now: float) -> MetricsSnapshot:
        """Build the metrics as seen at time ``now`` (epoch seconds)."""
        elapsed_s = 0.0 if self._start_time is None else max(0.0, now - self._start_time)
        return MetricsSnapshot(
            average_waiting_time_s=_mean(self._waiting_times),
            average_service_time_s=_mean(self._service_times),
            average_turnaround_time_s=_mean(self._turnaround_times),
            utilization_percent=self._utilization_percent(now, elapsed_s),
            throughput_per_minute=self._throughput_per_minute(elapsed_s),
            served_vehicles=len(self._service_times),
            waiting_vehicles=self._count_waiting_vehicles(),
        )

    def _register_parked(self, timeline: _VehicleTimeline, timestamp: float) -> None:
        timeline.parked_at = timestamp
        if timeline.waiting_at is not None:
            self._waiting_times.append(timestamp - timeline.waiting_at)

    def _register_exited(self, timeline: _VehicleTimeline, timestamp: float) -> None:
        timeline.exited_at = timestamp
        if timeline.parked_at is None:
            return  # Cancelled before obtaining a slot: not a served vehicle
        service_time = timestamp - timeline.parked_at
        self._service_times.append(service_time)
        self._closed_busy_seconds += service_time
        if timeline.waiting_at is not None:
            self._turnaround_times.append(timestamp - timeline.waiting_at)

    def _utilization_percent(self, now: float, elapsed_s: float) -> float:
        if elapsed_s <= 0:
            return 0.0
        open_busy_seconds = sum(
            max(0.0, now - timeline.parked_at)
            for timeline in self._timelines.values()
            if timeline.parked_at is not None and timeline.exited_at is None
        )
        busy_seconds = self._closed_busy_seconds + open_busy_seconds
        percent = busy_seconds / (self._capacity * elapsed_s) * _MAX_PERCENT
        return min(_MAX_PERCENT, max(0.0, percent))

    def _throughput_per_minute(self, elapsed_s: float) -> float:
        if elapsed_s <= 0:
            return 0.0
        return len(self._service_times) / (elapsed_s / _SECONDS_PER_MINUTE)

    def _count_waiting_vehicles(self) -> int:
        return sum(
            1
            for timeline in self._timelines.values()
            if timeline.waiting_at is not None
            and timeline.parked_at is None
            and timeline.exited_at is None
        )


def _mean(values: list[float]) -> float:
    """Arithmetic mean, or ``0.0`` for an empty list."""
    return sum(values) / len(values) if values else 0.0
