"""Tests for SimulationConfig defaults, immutability and validation."""

import unittest
from dataclasses import FrozenInstanceError

from src.config import DEFAULT_CONFIG, SimulationConfig, UiTheme


class TestSimulationConfigDefaults(unittest.TestCase):
    """Default configuration must be valid and immutable."""

    def test_default_config_is_a_simulation_config(self) -> None:
        self.assertIsInstance(DEFAULT_CONFIG, SimulationConfig)
        self.assertEqual(DEFAULT_CONFIG, SimulationConfig())

    def test_default_values(self) -> None:
        config = SimulationConfig()
        self.assertEqual(config.capacity, 5)
        self.assertEqual(config.initial_vehicles, 8)
        self.assertIsNone(config.seed)
        self.assertIsInstance(config.theme, UiTheme)

    def test_config_is_immutable(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            DEFAULT_CONFIG.capacity = 10  # type: ignore[misc]

    def test_custom_values_are_accepted(self) -> None:
        config = SimulationConfig(capacity=3, initial_vehicles=0, seed=42,
                                  arrival_time_range=(0.0, 0.0))
        self.assertEqual((config.capacity, config.seed), (3, 42))


class TestSimulationConfigValidation(unittest.TestCase):
    """Invalid parameters must raise ValueError on creation."""

    INVALID_KWARGS = (
        {"capacity": 0},
        {"initial_vehicles": -1},
        {"acquire_timeout_s": 0},
        {"ui_poll_interval_ms": 0},
        {"metrics_publish_interval_s": -1.0},
        {"logs_dir": "  "},
        {"arrival_time_range": (2.0, 1.0)},
        {"arrival_time_range": (-1.0, 1.0)},
        {"parking_time_range": (5.0, 3.0)},
        {"parking_time_range": (1.0, 2.0, 3.0)},
    )

    def test_invalid_parameters_raise_value_error(self) -> None:
        for kwargs in self.INVALID_KWARGS:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                SimulationConfig(**kwargs)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
