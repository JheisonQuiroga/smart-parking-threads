"""Unit and concurrency tests for ParkingManager."""

import threading
import time
import unittest
from typing import Optional

from src.core.parking_manager import ParkingManager


class TestParkingManagerInit(unittest.TestCase):
    """Validation of initialization parameters and initial state."""

    def test_valid_initialization(self) -> None:
        manager = ParkingManager(capacity=3, acquire_timeout_s=0.2)
        self.assertEqual(manager.capacity, 3)
        self.assertEqual(manager.acquire_timeout_s, 0.2)
        self.assertEqual(manager.occupied, 0)
        self.assertEqual(manager.available, 3)
        self.assertTrue(manager.is_empty)
        self.assertFalse(manager.is_full)
        self.assertEqual(manager.slots_snapshot(), (None, None, None))

    def test_invalid_capacity_raises_value_error(self) -> None:
        for invalid_capacity in (0, -1, -5):
            with self.subTest(capacity=invalid_capacity):
                with self.assertRaises(ValueError):
                    ParkingManager(capacity=invalid_capacity)

    def test_invalid_timeout_raises_value_error(self) -> None:
        for invalid_timeout in (0, -0.5, -1):
            with self.subTest(timeout=invalid_timeout):
                with self.assertRaises(ValueError):
                    ParkingManager(capacity=3, acquire_timeout_s=invalid_timeout)


class TestParkingManagerOperations(unittest.TestCase):
    """Testing single-threaded slot acquisition and release."""

    def setUp(self) -> None:
        self.manager = ParkingManager(capacity=2, acquire_timeout_s=0.05)

    def test_acquire_and_release_single_slot(self) -> None:
        slot = self.manager.try_acquire_slot(vehicle_id=101)
        self.assertEqual(slot, 0)
        self.assertEqual(self.manager.occupied, 1)
        self.assertEqual(self.manager.available, 1)
        self.assertFalse(self.manager.is_empty)
        self.assertFalse(self.manager.is_full)
        self.assertEqual(self.manager.get_slot_for_vehicle(101), 0)
        self.assertIsNone(self.manager.get_slot_for_vehicle(999))
        self.assertEqual(self.manager.slots_snapshot(), (101, None))

        self.manager.release_slot(slot=0, vehicle_id=101)
        self.assertEqual(self.manager.occupied, 0)
        self.assertEqual(self.manager.available, 2)
        self.assertTrue(self.manager.is_empty)
        self.assertEqual(self.manager.slots_snapshot(), (None, None))

    def test_acquire_until_full_then_timeout(self) -> None:
        slot1 = self.manager.try_acquire_slot(vehicle_id=1)
        slot2 = self.manager.try_acquire_slot(vehicle_id=2)
        self.assertEqual(slot1, 0)
        self.assertEqual(slot2, 1)
        self.assertEqual(self.manager.occupied, 2)
        self.assertEqual(self.manager.available, 0)
        self.assertTrue(self.manager.is_full)

        # Third attempt should time out
        start = time.time()
        slot3 = self.manager.try_acquire_slot(vehicle_id=3)
        elapsed = time.time() - start

        self.assertIsNone(slot3)
        self.assertGreaterEqual(elapsed, 0.04)

        # Release slot 0, then vehicle 3 can acquire it
        self.manager.release_slot(slot=0, vehicle_id=1)
        slot3_retry = self.manager.try_acquire_slot(vehicle_id=3)
        self.assertEqual(slot3_retry, 0)
        self.assertEqual(self.manager.slots_snapshot(), (3, 2))

    def test_duplicate_vehicle_id_raises_value_error(self) -> None:
        slot = self.manager.try_acquire_slot(vehicle_id=50)
        self.assertEqual(slot, 0)
        with self.assertRaises(ValueError):
            self.manager.try_acquire_slot(vehicle_id=50)

    def test_release_with_wrong_vehicle_id_raises_value_error(self) -> None:
        slot = self.manager.try_acquire_slot(vehicle_id=42)
        self.assertEqual(slot, 0)
        with self.assertRaises(ValueError):
            self.manager.release_slot(slot=0, vehicle_id=999)

    def test_release_out_of_bounds_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            self.manager.release_slot(slot=5, vehicle_id=1)
        with self.assertRaises(ValueError):
            self.manager.release_slot(slot=-1, vehicle_id=1)

    def test_reset_when_empty_succeeds(self) -> None:
        self.manager.try_acquire_slot(vehicle_id=1)
        self.manager.release_slot(slot=0, vehicle_id=1)
        self.manager.reset()
        self.assertEqual(self.manager.occupied, 0)
        self.assertTrue(self.manager.is_empty)

    def test_reset_when_occupied_raises_runtime_error(self) -> None:
        self.manager.try_acquire_slot(vehicle_id=1)
        with self.assertRaises(RuntimeError):
            self.manager.reset()


class TestParkingManagerConcurrency(unittest.TestCase):
    """Stress test with high concurrency to verify absence of race conditions."""

    def test_concurrent_slot_contention(self) -> None:
        capacity = 4
        num_vehicles = 24
        manager = ParkingManager(capacity=capacity, acquire_timeout_s=0.05)

        violations: list[str] = []
        completed_vehicles = 0
        lock = threading.Lock()

        def worker(v_id: int) -> None:
            nonlocal completed_vehicles
            for _ in range(3):
                slot: Optional[int] = None
                while slot is None:
                    slot = manager.try_acquire_slot(v_id)

                # Invariant checks inside critical section
                snapshot = manager.slots_snapshot()
                occ = manager.occupied
                if occ > capacity or occ < 0:
                    with lock:
                        violations.append(f"Occupancy out of bounds: {occ}")
                if snapshot.count(v_id) != 1:
                    with lock:
                        violations.append(f"Vehicle {v_id} not recorded exactly once in snapshot")

                # Hold slot briefly
                time.sleep(0.005)

                manager.release_slot(slot=slot, vehicle_id=v_id)

            with lock:
                completed_vehicles += 1

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(1, num_vehicles + 1)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        self.assertEqual(completed_vehicles, num_vehicles, "Not all threads completed")
        self.assertEqual(violations, [], f"Violations detected: {violations}")
        self.assertEqual(manager.occupied, 0)
        self.assertEqual(manager.slots_snapshot(), tuple([None] * capacity))


if __name__ == "__main__":
    unittest.main()
