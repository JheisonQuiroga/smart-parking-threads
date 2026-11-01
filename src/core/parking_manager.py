"""Parking resource manager governing concurrency, capacity, and slot allocation.

This class is the sole owner of the synchronization primitives:
- A :class:`threading.BoundedSemaphore` to enforce the capacity limit.
- A :class:`threading.Lock` protecting the critical section where slot assignments
  and occupancy counts are read and updated.
"""

import threading
from typing import Optional


class ParkingManager:
    """Manages slot allocation and concurrency for the parking lot.

    Attributes:
        capacity: Maximum number of concurrent vehicles allowed.
        acquire_timeout_s: Timeout in seconds for semaphore acquisition attempts.
    """

    def __init__(self, capacity: int, acquire_timeout_s: float = 0.5) -> None:
        """Initialize the parking manager with a fixed capacity and timeout.

        Args:
            capacity: Maximum number of parking slots (must be >= 1).
            acquire_timeout_s: Timeout in seconds for acquire attempts (must be > 0).

        Raises:
            ValueError: If capacity < 1 or acquire_timeout_s <= 0.
        """
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        if acquire_timeout_s <= 0:
            raise ValueError("acquire_timeout_s must be > 0")

        self._capacity: int = capacity
        self._acquire_timeout_s: float = acquire_timeout_s
        self._lock: threading.Lock = threading.Lock()
        self._semaphore: threading.BoundedSemaphore = threading.BoundedSemaphore(capacity)
        self._occupied: int = 0
        self._slots: list[Optional[int]] = [None] * capacity

    @property
    def capacity(self) -> int:
        """Total parking capacity."""
        return self._capacity

    @property
    def acquire_timeout_s(self) -> float:
        """Timeout in seconds for each acquire attempt."""
        return self._acquire_timeout_s

    @property
    def occupied(self) -> int:
        """Current number of occupied parking slots."""
        with self._lock:
            return self._occupied

    @property
    def available(self) -> int:
        """Current number of available parking slots."""
        with self._lock:
            return self._capacity - self._occupied

    @property
    def is_full(self) -> bool:
        """Return True if all parking slots are occupied."""
        with self._lock:
            return self._occupied >= self._capacity

    @property
    def is_empty(self) -> bool:
        """Return True if no parking slots are occupied."""
        with self._lock:
            return self._occupied == 0

    def get_slot_for_vehicle(self, vehicle_id: int) -> Optional[int]:
        """Look up the slot currently held by the given vehicle.

        Args:
            vehicle_id: Unique identifier of the vehicle to search for.

        Returns:
            The slot index if the vehicle is currently parked, else ``None``.
        """
        with self._lock:
            for index, occupant in enumerate(self._slots):
                if occupant == vehicle_id:
                    return index
            return None

    def try_acquire_slot(self, vehicle_id: int) -> Optional[int]:
        """Attempt to acquire a parking slot within the configured timeout.

        Args:
            vehicle_id: Unique identifier of the vehicle requesting entry.

        Returns:
            The zero-based index of the assigned parking slot if acquired, or
            ``None`` if the timeout elapsed while waiting in queue.

        Raises:
            ValueError: If the vehicle is already parked in another slot.
        """
        if not self._semaphore.acquire(timeout=self._acquire_timeout_s):
            return None

        with self._lock:
            # Prevent duplicate slot acquisitions by the same vehicle
            if vehicle_id in self._slots:
                self._semaphore.release()
                raise ValueError(
                    f"Vehicle {vehicle_id} is already parked in slot {self._slots.index(vehicle_id)}"
                )

            for index, occupant in enumerate(self._slots):
                if occupant is None:
                    self._slots[index] = vehicle_id
                    self._occupied += 1
                    return index

            # Fallback defensive programming: release if no free slot found
            self._semaphore.release()
            raise RuntimeError("Semaphore was acquired but no free slot was found")

    def release_slot(self, slot: int, vehicle_id: int) -> None:
        """Release a previously acquired parking slot.

        Args:
            slot: Index of the slot being vacated.
            vehicle_id: Identifier of the vehicle leaving the slot.

        Raises:
            ValueError: If the slot index is out of bounds or not occupied by
                the given vehicle.
        """
        with self._lock:
            if not 0 <= slot < self._capacity:
                raise ValueError(
                    f"Slot index {slot} is out of bounds (capacity: {self._capacity})"
                )
            if self._slots[slot] != vehicle_id:
                raise ValueError(
                    f"Slot {slot} is not occupied by vehicle {vehicle_id} "
                    f"(found {self._slots[slot]})"
                )

            self._slots[slot] = None
            self._occupied -= 1

        self._semaphore.release()

    def slots_snapshot(self) -> tuple[Optional[int], ...]:
        """Return a thread-safe snapshot of all parking slots.

        Returns:
            A tuple where each element is the occupant vehicle ID or ``None``.
        """
        with self._lock:
            return tuple(self._slots)

    def reset(self) -> None:
        """Reset the parking lot state to empty with a fresh semaphore.

        Raises:
            RuntimeError: If called while slots are still occupied.
        """
        with self._lock:
            if self._occupied > 0:
                raise RuntimeError(
                    f"Cannot reset ParkingManager while {self._occupied} slots are occupied"
                )
            self._slots = [None] * self._capacity
            self._occupied = 0
            self._semaphore = threading.BoundedSemaphore(self._capacity)
