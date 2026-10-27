"""Tests for the models layer: states, validation, immutability and pickling."""

import pickle
import unittest
from dataclasses import FrozenInstanceError

from src.models import (
    MetricsSnapshot,
    StopSignal,
    VehicleEvent,
    VehicleInfo,
    VehicleState,
)


class TestVehicleState(unittest.TestCase):
    """Lifecycle states mirror OS process states."""

    def test_states_are_defined_in_lifecycle_order(self) -> None:
        self.assertEqual(
            [state.name for state in VehicleState],
            ["ARRIVING", "WAITING", "PARKED", "EXITED"],
        )

    def test_only_exited_is_terminal(self) -> None:
        terminal = [state for state in VehicleState if state.is_terminal]
        self.assertEqual(terminal, [VehicleState.EXITED])


class TestVehicleInfo(unittest.TestCase):
    """Read model defaults and validation."""

    def test_defaults(self) -> None:
        info = VehicleInfo(vehicle_id=1)
        self.assertEqual(info.state, VehicleState.ARRIVING)
        self.assertIsNone(info.slot)
        self.assertEqual((info.waiting_time_s, info.parking_time_s), (0.0, 0.0))

    def test_invalid_values_raise_value_error(self) -> None:
        invalid_kwargs = (
            {"vehicle_id": 0},
            {"vehicle_id": 1, "slot": -1},
            {"vehicle_id": 1, "waiting_time_s": -0.1},
            {"vehicle_id": 1, "parking_time_s": -0.1},
        )
        for kwargs in invalid_kwargs:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                VehicleInfo(**kwargs)  # type: ignore[arg-type]


class TestMessagesArePicklableAndImmutable(unittest.TestCase):
    """Messages must cross multiprocessing.Queue unchanged and stay immutable."""

    def setUp(self) -> None:
        self.event = VehicleEvent(timestamp=1.5, vehicle_id=3, state=VehicleState.PARKED,
                                  slot=2, occupied=4, capacity=5)
        self.metrics = MetricsSnapshot(average_waiting_time_s=1.2, utilization_percent=80.0,
                                       served_vehicles=7, waiting_vehicles=2)

    def test_round_trip_through_pickle(self) -> None:
        for message in (self.event, self.metrics, StopSignal(), VehicleInfo(vehicle_id=9)):
            with self.subTest(message=type(message).__name__):
                self.assertEqual(pickle.loads(pickle.dumps(message)), message)

    def test_events_and_metrics_are_frozen(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            self.event.state = VehicleState.EXITED  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            self.metrics.served_vehicles = 0  # type: ignore[misc]

    def test_stop_signals_are_equal(self) -> None:
        self.assertEqual(StopSignal(), StopSignal())


if __name__ == "__main__":
    unittest.main()
