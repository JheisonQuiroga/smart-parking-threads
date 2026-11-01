"""Queue-based implementation of EventPublisher fanning out events across boundaries."""

import queue
from typing import Any, Optional

from src.models.events import VehicleEvent


class QueueEventPublisher:
    """Publishes vehicle events to an in-process UI queue and an inter-process telemetry queue.

    Attributes:
        ui_queue: Thread-safe queue read by the Tkinter main thread.
        telemetry_queue: Multiprocessing queue read by the background analytics process.
    """

    def __init__(
        self,
        ui_queue: "queue.Queue[VehicleEvent]",
        telemetry_queue: Optional[Any] = None,
    ) -> None:
        """Initialize publisher with target queues.

        Args:
            ui_queue: Thread-safe queue for UI updates.
            telemetry_queue: Optional multiprocessing queue for the telemetry worker.
        """
        self._ui_queue: "queue.Queue[VehicleEvent]" = ui_queue
        self._telemetry_queue: Optional[Any] = telemetry_queue

    @property
    def ui_queue(self) -> "queue.Queue[VehicleEvent]":
        """The UI queue."""
        return self._ui_queue

    @property
    def telemetry_queue(self) -> Optional[Any]:
        """The telemetry queue, or None if disabled."""
        return self._telemetry_queue

    def publish(self, event: VehicleEvent) -> None:
        """Deliver the event to the UI queue and telemetry queue.

        Args:
            event: The vehicle lifecycle event to publish.
        """
        self._ui_queue.put(event)

        if self._telemetry_queue is not None:
            try:
                # Use a small timeout to avoid unbounded blocking if the process pipe fills
                self._telemetry_queue.put(event, timeout=0.1)
            except (queue.Full, ValueError, OSError):
                # Process queue might be closed, terminating, or full during shutdown
                pass

    def clear_ui_queue(self) -> None:
        """Drain all pending events from the UI queue."""
        while not self._ui_queue.empty():
            try:
                self._ui_queue.get_nowait()
            except queue.Empty:
                break
