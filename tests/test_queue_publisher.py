"""Unit tests for QueueEventPublisher."""

import multiprocessing
import queue
import unittest

from src.core.queue_publisher import QueueEventPublisher
from src.models.events import VehicleEvent
from src.models.vehicle import VehicleState


class TestQueueEventPublisher(unittest.TestCase):
    """Verifies that events are fanned out to UI and telemetry queues."""

    def setUp(self) -> None:
        self.ui_queue: queue.Queue[VehicleEvent] = queue.Queue()
        self.telemetry_queue: multiprocessing.Queue = multiprocessing.Queue()
        self.publisher = QueueEventPublisher(
            ui_queue=self.ui_queue,
            telemetry_queue=self.telemetry_queue,
        )

    def tearDown(self) -> None:
        self.telemetry_queue.close()
        self.telemetry_queue.join_thread()

    def test_publish_to_both_queues(self) -> None:
        event = VehicleEvent(
            timestamp=123.45,
            vehicle_id=5,
            state=VehicleState.PARKED,
            slot=1,
            occupied=2,
            capacity=4,
        )

        self.publisher.publish(event)

        # Delivered to UI queue (in-memory queue.Queue is immediate)
        ui_event = self.ui_queue.get_nowait()
        self.assertEqual(ui_event, event)

        # Delivered to telemetry queue (uses OS pipe with feeder thread; wait with short timeout)
        telemetry_event = self.telemetry_queue.get(timeout=1.0)
        self.assertEqual(telemetry_event, event)

    def test_publish_with_no_telemetry_queue(self) -> None:
        solo_publisher = QueueEventPublisher(ui_queue=self.ui_queue, telemetry_queue=None)
        self.assertIsNone(solo_publisher.telemetry_queue)

        event = VehicleEvent(
            timestamp=100.0,
            vehicle_id=1,
            state=VehicleState.ARRIVING,
        )
        solo_publisher.publish(event)

        self.assertEqual(self.ui_queue.get_nowait(), event)


if __name__ == "__main__":
    unittest.main()
