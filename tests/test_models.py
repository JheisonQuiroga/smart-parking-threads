"""Tests for the models layer: states, validation, immutability and pickling."""

import pickle
import unittest
from dataclasses import FrozenInstanceError

from src.models import (
    EMPTY_METRICS,
    VEHICLE_EVENT_CSV_FIELDS,
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

    def test_only_waiting_is_blocked(self) -> None:
        blocked = [state for state in VehicleState if state.is_blocked]
        self.assertEqual(blocked, [VehicleState.WAITING])

    def test_only_parked_is_holding_slot(self) -> None:
        holding = [state for state in VehicleState if state.is_holding_slot]
        self.assertEqual(holding, [VehicleState.PARKED])

    def test_valid_state_transitions(self) -> None:
        valid_pairs = (
            (VehicleState.ARRIVING, VehicleState.WAITING),
            (VehicleState.ARRIVING, VehicleState.EXITED),
            (VehicleState.WAITING, VehicleState.WAITING),
            (VehicleState.WAITING, VehicleState.PARKED),
            (VehicleState.WAITING, VehicleState.EXITED),
            (VehicleState.PARKED, VehicleState.EXITED),
        )
        for source, target in valid_pairs:
            with self.subTest(source=source, target=target):
                self.assertTrue(source.can_transition_to(target))

    def test_invalid_state_transitions(self) -> None:
        invalid_pairs = (
            (VehicleState.ARRIVING, VehicleState.PARKED),
            (VehicleState.PARKED, VehicleState.WAITING),
            (VehicleState.PARKED, VehicleState.ARRIVING),
            (VehicleState.EXITED, VehicleState.ARRIVING),
            (VehicleState.EXITED, VehicleState.WAITING),
            (VehicleState.EXITED, VehicleState.PARKED),
            (VehicleState.EXITED, VehicleState.EXITED),
        )
        for source, target in invalid_pairs:
            with self.subTest(source=source, target=target):
                self.assertFalse(source.can_transition_to(target))


class TestVehicleInfo(unittest.TestCase):
    """Read model defaults, turnaround calculation and validation."""

    def test_defaults(self) -> None:
        info = VehicleInfo(vehicle_id=1)
        self.assertEqual(info.state, VehicleState.ARRIVING)
        self.assertIsNone(info.slot)
        self.assertEqual((info.waiting_time_s, info.parking_time_s), (0.0, 0.0))
        self.assertEqual(info.turnaround_time_s, 0.0)

    def test_turnaround_time_is_sum_of_waiting_and_parking(self) -> None:
        info = VehicleInfo(vehicle_id=2, waiting_time_s=1.5, parking_time_s=3.25)
        self.assertAlmostEqual(info.turnaround_time_s, 4.75)

    def test_non_enum_state_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            VehicleInfo(vehicle_id=1, state="arriving")  # type: ignore[arg-type]

    def test_invalid_values_raise_value_error(self) -> None:
        invalid_kwargs = (
            {"vehicle_id": 0},
            {"vehicle_id": -3},
            {"vehicle_id": 1, "slot": -1},
            {"vehicle_id": 1, "waiting_time_s": -0.1},
            {"vehicle_id": 1, "parking_time_s": -0.1},
        )
        for kwargs in invalid_kwargs:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                VehicleInfo(**kwargs)  # type: ignore[arg-type]


class TestVehicleEvent(unittest.TestCase):
    """Validation and CSV serialization of VehicleEvent."""

    def test_valid_event_and_csv_row(self) -> None:
        event = VehicleEvent(
            timestamp=10.5,
            vehicle_id=4,
            state=VehicleState.PARKED,
            slot=1,
            occupied=2,
            capacity=5,
        )
        self.assertEqual(
            event.to_csv_row(),
            (10.5, 4, "parked", 1, 2, 5),
        )
        self.assertEqual(len(event.to_csv_row()), len(VEHICLE_EVENT_CSV_FIELDS))

    def test_csv_row_uses_empty_string_when_slot_is_none(self) -> None:
        event = VehicleEvent(timestamp=1.0, vehicle_id=1, state=VehicleState.WAITING)
        self.assertEqual(event.to_csv_row()[3], "")

    def test_non_enum_state_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            VehicleEvent(timestamp=1.0, vehicle_id=1, state="waiting")  # type: ignore[arg-type]

    def test_invalid_event_fields_raise_value_error(self) -> None:
        base = {"timestamp": 1.0, "vehicle_id": 1, "state": VehicleState.PARKED}
        invalid_overrides = (
            {"timestamp": -0.1},
            {"vehicle_id": 0},
            {"capacity": -1},
            {"occupied": -1},
            {"occupied": 6, "capacity": 5},
            {"slot": -1},
            {"slot": 5, "capacity": 5},
        )
        for override in invalid_overrides:
            kwargs = {**base, **override}
            with self.subTest(override=override), self.assertRaises(ValueError):
                VehicleEvent(**kwargs)  # type: ignore[arg-type]


class TestMetricsSnapshot(unittest.TestCase):
    """Validation and defaults of MetricsSnapshot."""

    def test_empty_metrics_constant(self) -> None:
        self.assertEqual(EMPTY_METRICS, MetricsSnapshot())
        self.assertEqual(EMPTY_METRICS.served_vehicles, 0)

    def test_invalid_metrics_raise_value_error(self) -> None:
        invalid_kwargs = (
            {"average_waiting_time_s": -0.1},
            {"average_service_time_s": -0.1},
            {"average_turnaround_time_s": -0.1},
            {"utilization_percent": -1.0},
            {"utilization_percent": 100.1},
            {"throughput_per_minute": -0.5},
            {"served_vehicles": -1},
            {"waiting_vehicles": -1},
        )
        for kwargs in invalid_kwargs:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                MetricsSnapshot(**kwargs)  # type: ignore[arg-type]


class TestMessagesArePicklableAndImmutable(unittest.TestCase):
    """Messages must cross multiprocessing.Queue unchanged and stay immutable."""

    def setUp(self) -> None:
        self.event = VehicleEvent(
            timestamp=1.5,
            vehicle_id=3,
            state=VehicleState.PARKED,
            slot=2,
            occupied=4,
            capacity=5,
        )
        self.metrics = MetricsSnapshot(
            average_waiting_time_s=1.2,
            utilization_percent=80.0,
            served_vehicles=7,
            waiting_vehicles=2,
        )

    def test_round_trip_through_pickle(self) -> None:
        for message in (
            self.event,
            self.metrics,
            StopSignal(),
            VehicleInfo(vehicle_id=9),
        ):
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
