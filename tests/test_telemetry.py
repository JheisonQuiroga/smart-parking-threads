"""Tests for the telemetry layer: MetricsCalculator and TelemetryWorker process."""

import multiprocessing
import queue
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any

from src.config import SimulationConfig
from src.data.csv_repository import CsvEventRepository
from src.models.events import VehicleEvent
from src.models.metrics import MetricsSnapshot
from src.models.vehicle import VehicleState
from src.processes.metrics_calculator import MetricsCalculator
from src.processes.telemetry_proc import TelemetryWorker

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _event(vehicle_id: int, state: VehicleState, timestamp: float) -> VehicleEvent:
    return VehicleEvent(timestamp=timestamp, vehicle_id=vehicle_id, state=state)


class TestMetricsCalculator(unittest.TestCase):
    """OS scheduling formulas computed from synthetic event timelines."""

    def test_empty_calculator_returns_zero_metrics(self) -> None:
        calculator = MetricsCalculator(capacity=2, start_time=0.0)
        self.assertEqual(calculator.snapshot(now=0.0), MetricsSnapshot())
        self.assertEqual(calculator.snapshot(now=10.0), MetricsSnapshot())

    def test_full_scenario_metrics(self) -> None:
        calculator = MetricsCalculator(capacity=2, start_time=0.0)
        timeline = [
            # Vehicle 1: waits 0 s, parked 4 s
            (1, VehicleState.ARRIVING, 0.0), (1, VehicleState.WAITING, 1.0),
            (1, VehicleState.PARKED, 1.0), (1, VehicleState.EXITED, 5.0),
            # Vehicle 2: waits 2 s, parked 2 s
            (2, VehicleState.ARRIVING, 0.0), (2, VehicleState.WAITING, 2.0),
            (2, VehicleState.PARKED, 4.0), (2, VehicleState.EXITED, 6.0),
            # Vehicle 3: still blocked on the semaphore
            (3, VehicleState.WAITING, 3.0),
            # Vehicle 4: cancelled while waiting (not served)
            (4, VehicleState.WAITING, 3.0), (4, VehicleState.EXITED, 4.0),
            # Vehicle 5: waited 1 s and is still parked
            (5, VehicleState.WAITING, 7.0), (5, VehicleState.PARKED, 8.0),
        ]
        for vehicle_id, state, timestamp in timeline:
            calculator.register(_event(vehicle_id, state, timestamp))

        snapshot = calculator.snapshot(now=10.0)

        self.assertAlmostEqual(snapshot.average_waiting_time_s, 1.0)  # (0 + 2 + 1) / 3
        self.assertAlmostEqual(snapshot.average_service_time_s, 3.0)  # (4 + 2) / 2
        self.assertAlmostEqual(snapshot.average_turnaround_time_s, 4.0)  # (4 + 4) / 2
        self.assertAlmostEqual(snapshot.utilization_percent, 40.0)  # (4+2+2) / (2*10)
        self.assertAlmostEqual(snapshot.throughput_per_minute, 12.0)  # 2 / (10/60)
        self.assertEqual(snapshot.served_vehicles, 2)
        self.assertEqual(snapshot.waiting_vehicles, 1)

    def test_start_time_defaults_to_first_event(self) -> None:
        calculator = MetricsCalculator(capacity=1)
        calculator.register(_event(1, VehicleState.WAITING, 100.0))
        calculator.register(_event(1, VehicleState.PARKED, 100.0))
        calculator.register(_event(1, VehicleState.EXITED, 130.0))

        snapshot = calculator.snapshot(now=160.0)
        self.assertAlmostEqual(snapshot.utilization_percent, 50.0)  # 30 s busy of 60 s
        self.assertAlmostEqual(snapshot.throughput_per_minute, 1.0)

    def test_utilization_never_exceeds_one_hundred_percent(self) -> None:
        calculator = MetricsCalculator(capacity=1, start_time=10.0)
        calculator.register(_event(1, VehicleState.PARKED, 0.0))  # Parked before start
        self.assertEqual(calculator.snapshot(now=20.0).utilization_percent, 100.0)

    def test_invalid_capacity_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            MetricsCalculator(capacity=0)


class TestTelemetryWorkerProcess(unittest.TestCase):
    """The worker runs in a real child process and talks only through queues."""

    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.config = SimulationConfig(
            capacity=2,
            logs_dir=self._temp_dir.name,
            metrics_publish_interval_s=0.05,
        )
        self.event_queue: Any = multiprocessing.Queue()
        self.metrics_queue: Any = multiprocessing.Queue()

    def tearDown(self) -> None:
        for mp_queue in (self.event_queue, self.metrics_queue):
            mp_queue.close()
            mp_queue.join_thread()
        self._temp_dir.cleanup()

    def _drain_metrics(self) -> list[MetricsSnapshot]:
        snapshots: list[MetricsSnapshot] = []
        while True:
            try:
                snapshots.append(self.metrics_queue.get(timeout=0.5))
            except queue.Empty:
                return snapshots

    def test_processes_events_persists_csv_and_publishes_metrics(self) -> None:
        worker = TelemetryWorker(self.event_queue, self.metrics_queue, self.config)
        worker.start()
        start = time.time()
        events = [
            _event(1, VehicleState.WAITING, start),
            _event(1, VehicleState.PARKED, start + 0.1),
            _event(1, VehicleState.EXITED, start + 0.3),
        ]
        for event in events:
            self.event_queue.put(event)

        worker.stop_gracefully(timeout_s=3.0)

        self.assertFalse(worker.is_alive())
        self.assertEqual(worker.exitcode, 0)
        snapshots = self._drain_metrics()
        self.assertGreater(len(snapshots), 0)
        final = snapshots[-1]
        self.assertEqual(final.served_vehicles, 1)
        self.assertAlmostEqual(final.average_waiting_time_s, 0.1, places=3)
        self.assertAlmostEqual(final.average_service_time_s, 0.2, places=3)

        csv_files = list(Path(self._temp_dir.name).glob("*.csv"))
        self.assertEqual(len(csv_files), 1)
        self.assertEqual(CsvEventRepository.read_events(csv_files[0]), events)

    def test_publishes_periodic_snapshots_while_running(self) -> None:
        worker = TelemetryWorker(self.event_queue, self.metrics_queue, self.config)
        worker.start()
        try:
            first = self.metrics_queue.get(timeout=2.0)
            self.assertIsInstance(first, MetricsSnapshot)
        finally:
            worker.stop_gracefully(timeout_s=3.0)
        self.assertFalse(worker.is_alive())

    def test_forced_stop_event_ends_the_process(self) -> None:
        stop_event = multiprocessing.Event()
        worker = TelemetryWorker(self.event_queue, self.metrics_queue, self.config, stop_event)
        worker.start()
        stop_event.set()
        worker.join(timeout=3.0)

        self.assertFalse(worker.is_alive())
        self.assertEqual(worker.exitcode, 0)
        self._drain_metrics()

    def test_stop_gracefully_on_unstarted_worker_is_a_no_op(self) -> None:
        worker = TelemetryWorker(self.event_queue, self.metrics_queue, self.config)
        worker.stop_gracefully(timeout_s=0.1)
        self.assertFalse(worker.is_alive())


class TestSpawnSafety(unittest.TestCase):
    """A spawned child must never import Tkinter or the core threads (AGENTS.md 6)."""

    def test_telemetry_module_does_not_import_tkinter_or_core(self) -> None:
        check = (
            "import sys, src.processes.telemetry_proc; "
            "bad = [m for m in sys.modules if m == 'tkinter' or m.startswith('src.core') "
            "or m.startswith('src.views')]; "
            "sys.exit(1 if bad else 0)"
        )
        result = subprocess.run(
            [sys.executable, "-c", check], cwd=PROJECT_ROOT, capture_output=True, timeout=30
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode())


if __name__ == "__main__":
    unittest.main()
