"""Telemetry worker: a separate OS process for metrics and persistence.

Role in the simulator (AGENTS.md, rule 4): while the main process runs Tkinter
and the vehicle threads (shared memory + Semaphore/Lock), this process runs in
parallel with its own memory and GIL. It only communicates by message passing:

    main process --(VehicleEvent / StopSignal via event_queue)--> TelemetryWorker
    TelemetryWorker --(MetricsSnapshot via metrics_queue)--> main process

Spawn safety: this module imports only ``models``, ``data`` and ``config``, so a
child started with the ``spawn`` method never loads Tkinter or the core threads.
"""

import logging
import multiprocessing
import queue
import time
from multiprocessing.synchronize import Event as ProcessEvent
from typing import Any, Optional

from src.config import SimulationConfig
from src.data.csv_repository import CsvEventRepository
from src.models.events import StopSignal, VehicleEvent
from src.processes.metrics_calculator import MetricsCalculator

logger = logging.getLogger(__name__)

_QUEUE_POLL_INTERVAL_S = 0.1
_DEFAULT_JOIN_TIMEOUT_S = 2.0


class TelemetryWorker(multiprocessing.Process):
    """Process that computes OS metrics and persists every event to CSV."""

    def __init__(
        self,
        event_queue: Any,
        metrics_queue: Any,
        config: SimulationConfig,
        stop_event: Optional[ProcessEvent] = None,
    ) -> None:
        """Prepare the worker (it starts running only after :meth:`start`).

        Args:
            event_queue: ``multiprocessing.Queue`` with ``VehicleEvent`` and
                ``StopSignal`` messages coming from the main process.
            metrics_queue: ``multiprocessing.Queue`` where snapshots are published.
            config: Run configuration (capacity, logs directory, publish interval).
            stop_event: Optional ``multiprocessing.Event`` for an immediate stop
                without draining pending events.
        """
        super().__init__(name="TelemetryWorker", daemon=True)
        self._event_queue = event_queue
        self._metrics_queue = metrics_queue
        self._config = config
        self._stop_event = stop_event

    def run(self) -> None:
        """Main loop executed inside the child process."""
        calculator = MetricsCalculator(capacity=self._config.capacity, start_time=time.time())
        repository = CsvEventRepository(self._config.logs_dir)
        with repository:
            self._consume_until_stopped(calculator, repository)
        self._publish(calculator)  # Final snapshot with every processed event
        logger.info("Telemetry worker finished; events saved to %s", repository.path)

    def stop_gracefully(self, timeout_s: float = _DEFAULT_JOIN_TIMEOUT_S) -> None:
        """Called from the main process: drain pending events, then finish.

        Sends a :class:`StopSignal` (processed after every queued event), waits
        for the process and terminates it only if it does not exit in time, so
        no zombie process is left behind (AGENTS.md, rule 6).
        """
        if not self.is_alive():
            return
        self._event_queue.put(StopSignal())
        self.join(timeout=timeout_s)
        if self.is_alive():
            logger.warning("Telemetry worker did not stop in %.1fs; terminating", timeout_s)
            self.terminate()
            self.join(timeout=timeout_s)

    def _consume_until_stopped(
        self, calculator: MetricsCalculator, repository: CsvEventRepository
    ) -> None:
        next_publish_at = time.time() + self._config.metrics_publish_interval_s
        is_stop_requested = False
        while not is_stop_requested and not self._is_forced_stop():
            message = self._next_message()
            if isinstance(message, StopSignal):
                is_stop_requested = True
            elif isinstance(message, VehicleEvent):
                calculator.register(message)
                repository.append(message)
            elif message is not None:
                logger.warning("Ignoring unexpected telemetry message: %r", message)

            if time.time() >= next_publish_at:
                self._publish(calculator)
                next_publish_at = time.time() + self._config.metrics_publish_interval_s

    def _next_message(self) -> Optional[object]:
        try:
            return self._event_queue.get(timeout=_QUEUE_POLL_INTERVAL_S)
        except queue.Empty:
            return None

    def _is_forced_stop(self) -> bool:
        return self._stop_event is not None and self._stop_event.is_set()

    def _publish(self, calculator: MetricsCalculator) -> None:
        self._metrics_queue.put(calculator.snapshot(now=time.time()))
