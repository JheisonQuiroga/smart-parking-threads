"""Tests for CsvEventRepository (the isolated persistence layer)."""

import csv
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from src.data.csv_repository import CsvEventRepository
from src.models.events import VEHICLE_EVENT_CSV_FIELDS, VehicleEvent
from src.models.vehicle import VehicleState


def _event(vehicle_id: int, state: VehicleState, slot: int | None = None) -> VehicleEvent:
    return VehicleEvent(
        timestamp=1000.0 + vehicle_id,
        vehicle_id=vehicle_id,
        state=state,
        slot=slot,
        occupied=0 if slot is None else 1,
        capacity=3,
    )


class TestCsvEventRepository(unittest.TestCase):
    """Writing, reading and lifecycle of the CSV repository."""

    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.logs_dir = Path(self._temp_dir.name) / "nested" / "logs"

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_open_creates_directory_file_and_header(self) -> None:
        repository = CsvEventRepository(str(self.logs_dir))
        path = repository.open()
        repository.close()

        self.assertTrue(path.exists())
        self.assertEqual(path.parent, self.logs_dir)
        self.assertTrue(path.name.startswith("parking_events_"))
        with path.open(newline="", encoding="utf-8") as csv_file:
            self.assertEqual(tuple(next(csv.reader(csv_file))), VEHICLE_EVENT_CSV_FIELDS)

    def test_round_trip_preserves_events(self) -> None:
        events = [
            _event(1, VehicleState.WAITING),
            _event(1, VehicleState.PARKED, slot=2),
            _event(1, VehicleState.EXITED, slot=2),
        ]
        with CsvEventRepository(str(self.logs_dir)) as repository:
            repository.append(events[0])
            repository.append_many(events[1:])
            path = repository.path

        assert path is not None
        self.assertEqual(CsvEventRepository.read_events(path), events)

    def test_rows_are_flushed_before_close(self) -> None:
        repository = CsvEventRepository(str(self.logs_dir))
        path = repository.open()
        repository.append(_event(4, VehicleState.ARRIVING))

        self.assertEqual(len(CsvEventRepository.read_events(path)), 1)
        repository.close()

    def test_context_manager_closes_file(self) -> None:
        with CsvEventRepository(str(self.logs_dir)) as repository:
            self.assertTrue(repository.is_open)
        self.assertFalse(repository.is_open)
        repository.close()  # Closing twice must be harmless

    def test_append_without_open_raises_runtime_error(self) -> None:
        repository = CsvEventRepository(str(self.logs_dir))
        with self.assertRaises(RuntimeError):
            repository.append(_event(1, VehicleState.ARRIVING))

    def test_open_twice_raises_runtime_error(self) -> None:
        with CsvEventRepository(str(self.logs_dir)) as repository:
            with self.assertRaises(RuntimeError):
                repository.open()

    def test_each_run_gets_its_own_file(self) -> None:
        times = iter([datetime(2026, 1, 1, 10, 0, 0, 1), datetime(2026, 1, 1, 10, 0, 0, 2)])
        repository = CsvEventRepository(str(self.logs_dir), clock=lambda: next(times))
        with repository:
            first_path = repository.path
        with repository:
            second_path = repository.path

        self.assertNotEqual(first_path, second_path)
        self.assertEqual(len(list(self.logs_dir.glob("*.csv"))), 2)

    def test_read_events_rejects_foreign_csv(self) -> None:
        self.logs_dir.mkdir(parents=True)
        foreign = self.logs_dir / "foreign.csv"
        foreign.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            CsvEventRepository.read_events(foreign)

    def test_empty_arguments_raise_value_error(self) -> None:
        with self.assertRaises(ValueError):
            CsvEventRepository("  ")
        with self.assertRaises(ValueError):
            CsvEventRepository(str(self.logs_dir), file_prefix="")


if __name__ == "__main__":
    unittest.main()
