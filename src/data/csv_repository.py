"""CSV repository for vehicle events: the only component that touches the disk.

Following the Repository pattern, every read and write of event logs goes through
:class:`CsvEventRepository`, so no other layer opens files (AGENTS.md, rule 7).
"""

import csv
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Callable, Iterable, Optional, TextIO

from src.models.events import VEHICLE_EVENT_CSV_FIELDS, VehicleEvent
from src.models.vehicle import VehicleState

DEFAULT_FILE_PREFIX = "parking_events"
_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S_%f"


class CsvEventRepository:
    """Append-only CSV log of :class:`VehicleEvent` rows for one simulation run.

    Each call to :meth:`open` creates a new, uniquely named file inside
    ``logs_dir`` and writes the header defined by ``VEHICLE_EVENT_CSV_FIELDS``.
    """

    def __init__(
        self,
        logs_dir: str,
        file_prefix: str = DEFAULT_FILE_PREFIX,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        """Configure where the CSV files are written.

        Args:
            logs_dir: Directory for the CSV files (created if missing).
            file_prefix: Prefix of every generated file name.
            clock: Time source used to build unique file names (injectable for tests).

        Raises:
            ValueError: If ``logs_dir`` or ``file_prefix`` is empty.
        """
        if not logs_dir.strip():
            raise ValueError("logs_dir must not be empty")
        if not file_prefix.strip():
            raise ValueError("file_prefix must not be empty")

        self._logs_dir = Path(logs_dir)
        self._file_prefix = file_prefix
        self._clock = clock
        self._file: Optional[TextIO] = None
        self._writer: Optional[Any] = None  # csv.writer object (private type in stdlib)
        self._path: Optional[Path] = None

    @property
    def path(self) -> Optional[Path]:
        """Path of the current (or last) CSV file, or ``None`` if never opened."""
        return self._path

    @property
    def is_open(self) -> bool:
        """Return ``True`` while the repository accepts new rows."""
        return self._file is not None

    def open(self) -> Path:
        """Create a new CSV file and write its header.

        Returns:
            Path of the created file.

        Raises:
            RuntimeError: If the repository is already open.
        """
        if self.is_open:
            raise RuntimeError("CsvEventRepository is already open")

        self._logs_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"{self._file_prefix}_{self._clock().strftime(_TIMESTAMP_FORMAT)}.csv"
        self._path = self._logs_dir / file_name
        self._file = self._path.open("x", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        self._writer.writerow(VEHICLE_EVENT_CSV_FIELDS)
        self._file.flush()
        return self._path

    def append(self, event: VehicleEvent) -> None:
        """Write one event and flush it so the log survives abrupt shutdowns.

        Raises:
            RuntimeError: If the repository is not open.
        """
        self.append_many((event,))

    def append_many(self, events: Iterable[VehicleEvent]) -> None:
        """Write several events with a single flush.

        Raises:
            RuntimeError: If the repository is not open.
        """
        if self._file is None or self._writer is None:
            raise RuntimeError("CsvEventRepository is not open; call open() first")
        self._writer.writerows(event.to_csv_row() for event in events)
        self._file.flush()

    def close(self) -> None:
        """Close the current file. Safe to call more than once."""
        if self._file is not None:
            self._file.close()
        self._file = None
        self._writer = None

    def __enter__(self) -> "CsvEventRepository":
        """Open the repository when entering a ``with`` block."""
        self.open()
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        """Close the repository when leaving a ``with`` block."""
        self.close()

    @staticmethod
    def read_events(path: Path) -> list[VehicleEvent]:
        """Load every event stored in a CSV file written by this repository.

        Args:
            path: CSV file produced by :meth:`open` / :meth:`append`.

        Returns:
            The events in file order.

        Raises:
            ValueError: If the header does not match ``VEHICLE_EVENT_CSV_FIELDS``.
        """
        with path.open(newline="", encoding="utf-8") as csv_file:
            reader = csv.DictReader(csv_file)
            if tuple(reader.fieldnames or ()) != VEHICLE_EVENT_CSV_FIELDS:
                raise ValueError(f"Unexpected CSV header in {path}")
            return [_row_to_event(row) for row in reader]


def _row_to_event(row: dict[str, str]) -> VehicleEvent:
    """Convert a CSV row (as strings) back into a :class:`VehicleEvent`."""
    return VehicleEvent(
        timestamp=float(row["timestamp"]),
        vehicle_id=int(row["vehicle_id"]),
        state=VehicleState(row["state"]),
        slot=int(row["slot"]) if row["slot"] else None,
        occupied=int(row["occupied"]),
        capacity=int(row["capacity"]),
    )
