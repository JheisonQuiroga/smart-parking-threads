"""Simulation configuration: single, immutable source of truth for every layer."""

from dataclasses import dataclass, field
from typing import Optional

TimeRange = tuple[float, float]
"""Closed interval ``(min_seconds, max_seconds)`` used to draw random durations."""


@dataclass(frozen=True)
class UiTheme:
    """Color palette used by the views."""

    free_slot_color: str = "#4caf50"
    occupied_slot_color: str = "#e53935"
    background_color: str = "#1e1e2e"


@dataclass(frozen=True)
class SimulationConfig:
    """Parameters of a simulation run, validated on creation.

    Attributes:
        capacity: Number of parking slots (semaphore initial value).
        initial_vehicles: Vehicles spawned when the simulation starts.
        arrival_time_range: Random delay before a vehicle requests a slot.
        parking_time_range: Random time a vehicle stays parked.
        seed: Seed for reproducible runs; ``None`` means non-deterministic.
        acquire_timeout_s: Timeout of each ``semaphore.acquire`` attempt.
        ui_poll_interval_ms: Period of the Tkinter ``after`` polling loop.
        metrics_publish_interval_s: Period at which telemetry publishes snapshots.
        logs_dir: Directory where the persistence layer writes CSV files.
        theme: Color palette for the views.

    Raises:
        ValueError: If any parameter is out of its valid range.
    """

    capacity: int = 5
    initial_vehicles: int = 8
    arrival_time_range: TimeRange = (0.5, 4.0)
    parking_time_range: TimeRange = (3.0, 8.0)
    seed: Optional[int] = None
    acquire_timeout_s: float = 0.5
    ui_poll_interval_ms: int = 100
    metrics_publish_interval_s: float = 1.0
    logs_dir: str = "logs"
    theme: UiTheme = field(default_factory=UiTheme)

    def __post_init__(self) -> None:
        """Validate every parameter right after construction."""
        _require(self.capacity >= 1, "capacity must be >= 1")
        _require(self.initial_vehicles >= 0, "initial_vehicles must be >= 0")
        _require(self.acquire_timeout_s > 0, "acquire_timeout_s must be > 0")
        _require(self.ui_poll_interval_ms > 0, "ui_poll_interval_ms must be > 0")
        _require(
            self.metrics_publish_interval_s > 0,
            "metrics_publish_interval_s must be > 0",
        )
        _require(bool(self.logs_dir.strip()), "logs_dir must not be empty")
        _validate_time_range("arrival_time_range", self.arrival_time_range)
        _validate_time_range("parking_time_range", self.parking_time_range)


def _require(condition: bool, message: str) -> None:
    """Raise ``ValueError`` with ``message`` when ``condition`` is false."""
    if not condition:
        raise ValueError(message)


def _validate_time_range(name: str, time_range: TimeRange) -> None:
    """Ensure ``time_range`` is a pair satisfying ``0 <= min <= max``."""
    _require(len(time_range) == 2, f"{name} must have exactly two values")
    low, high = time_range
    _require(0 <= low <= high, f"{name} must satisfy 0 <= min <= max")


DEFAULT_CONFIG = SimulationConfig()
"""Default configuration used when the user does not customize the run."""
