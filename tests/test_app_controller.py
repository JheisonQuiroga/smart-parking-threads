"""Unit tests for the AppController facade."""

import tempfile
import threading
import time
import unittest

from src.config import SimulationConfig
from src.core.app_controller import AppController
from src.models.metrics import MetricsSnapshot
from src.models.vehicle import VehicleState


class TestAppControllerLifecycle(unittest.TestCase):
    """Test start, add_vehicle, stop, reset, telemetry and event draining in AppController."""

    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.fast_config = SimulationConfig(
            capacity=3,
            initial_vehicles=2,
            arrival_time_range=(0.01, 0.02),
            parking_time_range=(0.02, 0.04),
            acquire_timeout_s=0.02,
            metrics_publish_interval_s=0.05,
            logs_dir=self._temp_dir.name,
        )
        self.controller = AppController(config=self.fast_config)

    def tearDown(self) -> None:
        self.controller.shutdown()
        self._temp_dir.cleanup()

    def test_initial_state(self) -> None:
        self.assertFalse(self.controller.is_running)
        self.assertEqual(self.controller.capacity, 3)
        self.assertEqual(self.controller.occupied, 0)
        self.assertEqual(self.controller.available, 3)
        self.assertEqual(self.controller.active_threads_count, 0)
        self.assertEqual(self.controller.slots_snapshot(), (None, None, None))
        self.assertFalse(self.controller.is_telemetry_alive)

    def test_start_and_drain_events_and_metrics(self) -> None:
        self.controller.start()
        self.assertTrue(self.controller.is_running)
        self.assertEqual(self.controller.active_threads_count, 2)
        self.assertTrue(self.controller.is_telemetry_alive)

        # Allow some events and metrics to be generated
        time.sleep(0.15)

        events = self.controller.drain_ui_events()
        self.assertGreater(len(events), 0)
        vehicle_ids = {e.vehicle_id for e in events}
        self.assertTrue(vehicle_ids.issubset({1, 2}))

        metrics = self.controller.drain_metrics()
        # Telemetry worker should have emitted at least one snapshot
        if metrics is not None:
            self.assertIsInstance(metrics, MetricsSnapshot)

        self.controller.stop()
        self.assertFalse(self.controller.is_running)
        self.assertEqual(self.controller.active_threads_count, 0)
        self.assertFalse(self.controller.is_telemetry_alive)

    def test_add_vehicle_dynamically(self) -> None:
        self.controller.start()
        new_id = self.controller.add_vehicle()
        self.assertEqual(new_id, 3)
        self.assertEqual(self.controller.active_threads_count, 3)

        self.controller.stop()
        self.assertFalse(self.controller.is_running)

    def test_add_vehicle_while_stopped_raises_error(self) -> None:
        with self.assertRaises(RuntimeError):
            self.controller.add_vehicle()

    def test_start_while_running_raises_error(self) -> None:
        self.controller.start()
        with self.assertRaises(RuntimeError):
            self.controller.start()

    def test_previous_run_stop_event_is_never_cleared(self) -> None:
        self.controller.start()
        first_run_event = self.controller._stop_event
        self.controller.reset()
        self.controller.start()

        self.assertTrue(first_run_event.is_set(), "Old threads must stay signaled to stop")
        self.assertIsNot(self.controller._stop_event, first_run_event)
        self.assertFalse(self.controller._stop_event.is_set())

    def test_stop_does_not_hold_threads_lock_while_joining(self) -> None:
        self.controller.start()
        # A thread that ignores the stop event keeps stop() busy inside join()
        slow_thread = threading.Thread(target=time.sleep, args=(0.5,), daemon=True)
        slow_thread.start()
        with self.controller._threads_lock:
            self.controller._threads.append(slow_thread)  # type: ignore[arg-type]

        stopper = threading.Thread(target=self.controller.stop)
        stopper.start()
        time.sleep(0.1)  # stop() is now waiting on slow_thread.join()

        self.assertTrue(stopper.is_alive(), "stop() should still be joining")
        acquired = self.controller._threads_lock.acquire(timeout=0.1)
        if acquired:
            self.controller._threads_lock.release()
        stopper.join(timeout=2.0)

        self.assertTrue(acquired, "threads lock must be free while stop() joins")
        self.assertFalse(self.controller.is_running)

    def test_reset_restores_clean_state(self) -> None:
        self.controller.start()
        time.sleep(0.05)
        self.controller.reset()

        self.assertFalse(self.controller.is_running)
        self.assertEqual(self.controller.occupied, 0)
        self.assertEqual(self.controller.active_threads_count, 0)
        self.assertEqual(len(self.controller.drain_ui_events()), 0)
        self.assertIsNone(self.controller.drain_metrics())


if __name__ == "__main__":
    unittest.main()
