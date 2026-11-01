"""Unit tests for VehicleThread lifecycle, state transitions, and cancellation."""

import threading
import time
import unittest
from typing import Optional

from src.config import SimulationConfig
from src.core.parking_manager import ParkingManager
from src.core.vehicle_thread import VehicleThread
from src.models.events import VehicleEvent
from src.models.vehicle import VehicleState


class RecordingEventPublisher:
    """In-memory event publisher collecting events for test assertions."""

    def __init__(self) -> None:
        self.events: list[VehicleEvent] = []
        self._lock = threading.Lock()

    def publish(self, event: VehicleEvent) -> None:
        with self._lock:
            self.events.append(event)

    def get_events(self) -> list[VehicleEvent]:
        with self._lock:
            return list(self.events)


class TestVehicleThreadLifecycle(unittest.TestCase):
    """Test standard and interrupted lifecycle states of VehicleThread."""

    def setUp(self) -> None:
        self.config = SimulationConfig(
            capacity=2,
            arrival_time_range=(0.01, 0.02),
            parking_time_range=(0.01, 0.02),
            acquire_timeout_s=0.02,
        )
        self.parking = ParkingManager(capacity=2, acquire_timeout_s=0.02)
        self.publisher = RecordingEventPublisher()
        self.stop_event = threading.Event()

    def test_full_successful_lifecycle(self) -> None:
        thread = VehicleThread(
            vehicle_id=1,
            parking=self.parking,
            publisher=self.publisher,
            config=self.config,
            stop_event=self.stop_event,
        )
        thread.start()
        thread.join(timeout=2.0)

        self.assertFalse(thread.is_alive())
        events = self.publisher.get_events()
        states = [e.state for e in events]

        self.assertEqual(
            states,
            [
                VehicleState.ARRIVING,
                VehicleState.WAITING,
                VehicleState.PARKED,
                VehicleState.EXITED,
            ],
        )

        # Check slot assignments in events
        self.assertIsNone(events[0].slot)
        self.assertIsNone(events[1].slot)
        self.assertIsNotNone(events[2].slot)
        self.assertEqual(events[2].slot, events[3].slot)
        self.assertEqual(self.parking.occupied, 0)

    def test_cancellation_during_arrival(self) -> None:
        long_arrival_config = SimulationConfig(
            capacity=2,
            arrival_time_range=(2.0, 3.0),
            parking_time_range=(0.01, 0.02),
        )
        thread = VehicleThread(
            vehicle_id=2,
            parking=self.parking,
            publisher=self.publisher,
            config=long_arrival_config,
            stop_event=self.stop_event,
        )
        thread.start()
        time.sleep(0.05)
        self.stop_event.set()
        thread.join(timeout=1.0)

        self.assertFalse(thread.is_alive())
        states = [e.state for e in self.publisher.get_events()]
        self.assertEqual(states, [VehicleState.ARRIVING, VehicleState.EXITED])
        self.assertEqual(self.parking.occupied, 0)

    def test_cancellation_while_waiting_in_full_queue(self) -> None:
        # Fill all parking slots first
        slot0 = self.parking.try_acquire_slot(vehicle_id=901)
        slot1 = self.parking.try_acquire_slot(vehicle_id=902)
        self.assertEqual(self.parking.occupied, 2)

        thread = VehicleThread(
            vehicle_id=3,
            parking=self.parking,
            publisher=self.publisher,
            config=self.config,
            stop_event=self.stop_event,
        )
        thread.start()

        # Wait until thread reaches WAITING state
        deadline = time.time() + 1.0
        while time.time() < deadline:
            states = [e.state for e in self.publisher.get_events()]
            if VehicleState.WAITING in states:
                break
            time.sleep(0.01)

        self.assertIn(VehicleState.WAITING, [e.state for e in self.publisher.get_events()])

        # Signal stop while thread is still blocked waiting
        self.stop_event.set()
        thread.join(timeout=1.0)

        self.assertFalse(thread.is_alive())
        states = [e.state for e in self.publisher.get_events()]
        self.assertEqual(
            states,
            [VehicleState.ARRIVING, VehicleState.WAITING, VehicleState.EXITED],
        )

        # Cleanup held slots
        assert slot0 is not None and slot1 is not None
        self.parking.release_slot(slot0, 901)
        self.parking.release_slot(slot1, 902)
        self.assertEqual(self.parking.occupied, 0)

    def test_cancellation_while_parked(self) -> None:
        long_park_config = SimulationConfig(
            capacity=2,
            arrival_time_range=(0.01, 0.02),
            parking_time_range=(5.0, 6.0),
        )
        thread = VehicleThread(
            vehicle_id=4,
            parking=self.parking,
            publisher=self.publisher,
            config=long_park_config,
            stop_event=self.stop_event,
        )
        thread.start()

        # Wait until vehicle is parked
        deadline = time.time() + 1.0
        while time.time() < deadline:
            states = [e.state for e in self.publisher.get_events()]
            if VehicleState.PARKED in states:
                break
            time.sleep(0.01)

        self.assertEqual(self.parking.occupied, 1)

        # Trigger cancellation while parked
        self.stop_event.set()
        thread.join(timeout=1.0)

        self.assertFalse(thread.is_alive())
        self.assertEqual(self.parking.occupied, 0, "Slot must be freed even on cancellation")
        states = [e.state for e in self.publisher.get_events()]
        self.assertEqual(
            states,
            [
                VehicleState.ARRIVING,
                VehicleState.WAITING,
                VehicleState.PARKED,
                VehicleState.EXITED,
            ],
        )

    def test_invalid_vehicle_id_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            VehicleThread(
                vehicle_id=0,
                parking=self.parking,
                publisher=self.publisher,
                config=self.config,
                stop_event=self.stop_event,
            )


if __name__ == "__main__":
    unittest.main()
