"""Output ports (interfaces) for the core simulation layer.

In accordance with Dependency Inversion (DIP), core components depend on these
protocols rather than concrete queue or GUI implementations.
"""

import threading
from typing import Protocol

from src.models.events import VehicleEvent


class EventPublisher(Protocol):
    """Output port used by vehicle threads and managers to emit lifecycle events."""

    def publish(self, event: VehicleEvent) -> None:
        """Publish a vehicle lifecycle event to downstream subscribers.

        Args:
            event: The vehicle state transition event.
        """
        ...


class InMemoryEventPublisher:
    """Thread-safe in-memory event publisher useful for testing and headless runs."""

    def __init__(self) -> None:
        """Initialize an empty in-memory event store."""
        self._events: list[VehicleEvent] = []
        self._lock: threading.Lock = threading.Lock()

    def publish(self, event: VehicleEvent) -> None:
        """Store the published event in memory.

        Args:
            event: The vehicle state transition event.
        """
        with self._lock:
            self._events.append(event)

    def get_events(self) -> list[VehicleEvent]:
        """Return a copy of all published events recorded so far.

        Returns:
            A list of all recorded :class:`VehicleEvent` instances.
        """
        with self._lock:
            return list(self._events)

    def clear(self) -> None:
        """Clear all recorded events."""
        with self._lock:
            self._events.clear()
