"""Real parallelism with multiprocessing: telemetry worker and OS metrics."""

from src.processes.metrics_calculator import MetricsCalculator
from src.processes.telemetry_proc import TelemetryWorker

__all__ = ["MetricsCalculator", "TelemetryWorker"]
