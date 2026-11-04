"""Unit tests for the views layer (Tkinter widgets and window assembly)."""

import time
import tkinter as tk
import unittest

from src.config import SimulationConfig
from src.core.app_controller import AppController
from main import build_app
from src.models.events import VehicleEvent
from src.models.metrics import MetricsSnapshot
from src.models.vehicle import VehicleState
from src.views.app_window import MainWindow
from src.views.widgets import (
    ControlPanel,
    EventConsole,
    IconHelper,
    MetricsPanel,
    ParkingGrid,
    VehicleTable,
)


class TestViewsWidgets(unittest.TestCase):
    """Test individual Tkinter widgets and icon loading."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = tk.Tk()
        cls.root.withdraw()  # Hide root window during tests

    @classmethod
    def tearDownClass(cls) -> None:
        cls.root.destroy()

    def test_icon_helper_loads_assets(self) -> None:
        car_icon = IconHelper.get_icon("car.png", 48, 48)
        parking_icon = IconHelper.get_icon("parking.png", 48, 48)

        self.assertIsNotNone(car_icon)
        self.assertIsNotNone(parking_icon)
        self.assertEqual(car_icon.width(), 48)
        self.assertEqual(parking_icon.width(), 48)

    def test_control_panel_parse_config(self) -> None:
        config = SimulationConfig(capacity=4, initial_vehicles=6)
        panel = ControlPanel(
            self.root,
            default_config=config,
            on_start=lambda c: None,
            on_add=lambda: None,
            on_stop=lambda: None,
            on_reset=lambda: None,
        )

        parsed = panel.get_config()
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.capacity, 4)
        self.assertEqual(parsed.initial_vehicles, 6)

        panel.set_running_state(True)
        self.assertEqual(panel.btn_start["state"], "disabled")
        self.assertEqual(panel.btn_stop["state"], "normal")

        panel.set_running_state(False)
        self.assertEqual(panel.btn_start["state"], "normal")
        self.assertEqual(panel.btn_stop["state"], "disabled")
        panel.destroy()

    def test_parking_grid_render_slots(self) -> None:
        grid = ParkingGrid(self.root)
        grid.update_slots((None, 1, None), capacity=3)
        self.assertEqual(len(grid._slot_cards), 3)

        # Update again with capacity 4
        grid.update_slots((1, 2, None, None), capacity=4)
        self.assertEqual(len(grid._slot_cards), 4)
        grid.destroy()

    def test_metrics_panel_update(self) -> None:
        panel = MetricsPanel(self.root)
        snapshot = MetricsSnapshot(
            average_waiting_time_s=1.23,
            average_service_time_s=4.56,
            average_turnaround_time_s=5.79,
            utilization_percent=75.5,
            throughput_per_minute=10.2,
            served_vehicles=5,
            waiting_vehicles=2,
        )
        panel.update_metrics(snapshot)
        self.assertEqual(panel._cards["wait_time"]["text"], "1.23 s")
        self.assertEqual(panel._cards["utilization"]["text"], "75.5 %")
        self.assertEqual(panel._cards["served"]["text"], "5")
        panel.destroy()

    def test_vehicle_table_update_and_clear(self) -> None:
        table = VehicleTable(self.root)
        event = VehicleEvent(
            timestamp=time.time(),
            vehicle_id=7,
            state=VehicleState.PARKED,
            slot=2,
            occupied=1,
            capacity=4,
        )
        table.update_from_event(event)
        self.assertTrue(table.tree.exists("7"))

        table.clear()
        self.assertFalse(table.tree.exists("7"))
        table.destroy()

    def test_event_console_log(self) -> None:
        console = EventConsole(self.root)
        event = VehicleEvent(
            timestamp=time.time(),
            vehicle_id=3,
            state=VehicleState.WAITING,
        )
        console.log_event(event)
        console.log_system("Mensaje de prueba")

        content = console.text_area.get("1.0", "end")
        self.assertIn("Vehículo #3", content)
        self.assertIn("Mensaje de prueba", content)

        console.clear()
        self.assertEqual(console.text_area.get("1.0", "end").strip(), "")
        console.destroy()


class TestMainWindowIntegration(unittest.TestCase):
    """Test full MainWindow composition with AppController."""

    def test_build_app_and_destroy(self) -> None:
        root, controller, window = build_app()
        self.assertIsInstance(root, tk.Tk)
        self.assertIsInstance(controller, AppController)
        self.assertIsInstance(window, MainWindow)

        window._on_close()


if __name__ == "__main__":
    unittest.main()
