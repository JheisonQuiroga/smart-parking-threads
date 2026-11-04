"""MainWindow orchestrator: builds layout, connects widgets to AppController, and polls events."""

import tkinter as tk
from tkinter import ttk
from typing import Optional

from src.config import SimulationConfig
from src.core.app_controller import AppController
from src.models.metrics import MetricsSnapshot
from src.views.widgets import (
    ControlPanel,
    EventConsole,
    MetricsPanel,
    ParkingGrid,
    VehicleTable,
)


class MainWindow:
    """Main application window for the Smart Parking simulator.

    Adheres strictly to MVC: does not manage locks, threads, or processes.
    It reads state solely through AppController public methods and polls queues
    using the Tkinter event loop (.after).
    """

    def __init__(self, root: tk.Tk, controller: AppController) -> None:
        """Initialize the window and setup all visual components.

        Args:
            root: Root Tkinter window.
            controller: Simulation facade controller.
        """
        self._root = root
        self._controller = controller

        self._configure_window()
        self._configure_styles()
        self._build_layout()
        self._bind_protocols()

        # Start periodic polling loop (every 100ms per AGENTS.md rule 5)
        self._poll_job: Optional[str] = None
        self._schedule_poll()

    def _configure_window(self) -> None:
        self._root.title("Simulador de Parqueadero Inteligente — SO y Arquitectura de Computadores")
        self._root.geometry("1180x880")
        self._root.minsize(980, 720)
        self._root.configure(bg="#1e1e2e")

    def _configure_styles(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # Dark theme styling for Treeview
        style.configure(
            "Treeview",
            background="#181825",
            foreground="#cdd6f4",
            fieldbackground="#181825",
            rowheight=24,
            font=("Segoe UI", 9),
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background="#252538",
            foreground="#cdd6f4",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
        )
        style.map("Treeview.Heading", background=[("active", "#313244")])
        style.map(
            "Treeview",
            background=[("selected", "#313244")],
            foreground=[("selected", "#ffffff")],
        )

        # Scrollbar styling
        style.configure(
            "Vertical.TScrollbar",
            gripcount=0,
            background="#313244",
            troughcolor="#181825",
            bordercolor="#181825",
            arrowcolor="#a6adc8",
        )

    def _build_layout(self) -> None:
        # 1. Header Frame
        header = tk.Frame(self._root, bg="#181825", bd=1, relief="solid", padx=16, pady=10)
        header.pack(fill="x", padx=12, pady=(10, 6))

        title_box = tk.Frame(header, bg="#181825")
        title_box.pack(side="left")

        title_lbl = tk.Label(
            title_box,
            text="🅿️ SIMULADOR DE PARQUEADERO INTELIGENTE",
            font=("Segoe UI", 14, "bold"),
            fg="#cdd6f4",
            bg="#181825",
        )
        title_lbl.pack(anchor="w")

        subtitle_lbl = tk.Label(
            title_box,
            text=(
                "Concurrencia SO: Hilos (Vehículos) • Semáforo (Capacidad) • "
                "Lock (Exclusión Mutua) • Multiprocessing (Telemetría)"
            ),
            font=("Segoe UI", 8),
            fg="#a6adc8",
            bg="#181825",
        )
        subtitle_lbl.pack(anchor="w")

        self.status_badge = tk.Label(
            header,
            text="● DETENIDO",
            font=("Segoe UI", 10, "bold"),
            fg="#f38ba8",
            bg="#252538",
            padx=10,
            pady=4,
            bd=1,
            relief="solid",
        )
        self.status_badge.pack(side="right")

        # 2. Main content area (split top and bottom)
        main_content = tk.Frame(self._root, bg="#1e1e2e")
        main_content.pack(fill="both", expand=True, padx=12, pady=4)

        # Top Section: Controls + Parking Grid
        top_frame = tk.Frame(main_content, bg="#1e1e2e")
        top_frame.pack(fill="x", expand=False, pady=(0, 6))

        # Left of top: Control panel
        self.control_panel = ControlPanel(
            top_frame,
            default_config=self._controller.config,
            on_start=self._on_start,
            on_add=self._on_add_vehicle,
            on_stop=self._on_stop,
            on_reset=self._on_reset,
        )
        self.control_panel.pack(side="left", fill="both", expand=False, padx=(0, 6))

        # Right of top: Parking Bay Grid
        self.parking_grid = ParkingGrid(top_frame)
        self.parking_grid.pack(side="right", fill="both", expand=True)

        # 3. Middle Section: Real-time OS Metrics (multiprocessing KPI dashboard)
        self.metrics_panel = MetricsPanel(main_content)
        self.metrics_panel.pack(fill="x", pady=(0, 6))

        # 4. Bottom Section: Split between Vehicle Table and Event Console
        bottom_frame = tk.Frame(main_content, bg="#1e1e2e")
        bottom_frame.pack(fill="both", expand=True)

        self.vehicle_table = VehicleTable(bottom_frame)
        self.vehicle_table.pack(side="left", fill="both", expand=True, padx=(0, 6))

        self.event_console = EventConsole(bottom_frame)
        self.event_console.pack(side="right", fill="both", expand=True)

        # Initial slots rendering
        self.parking_grid.update_slots(
            self._controller.slots_snapshot(),
            self._controller.capacity,
        )

    def _bind_protocols(self) -> None:
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _schedule_poll(self) -> None:
        poll_interval = self._controller.config.ui_poll_interval_ms
        self._poll_job = self._root.after(poll_interval, self._poll_events)

    def _poll_events(self) -> None:
        """Periodic consumer of the UI and metrics queues (running in Tkinter thread)."""
        # 1. Drain and render vehicle events from threads
        events = self._controller.drain_ui_events()
        for event in events:
            self.vehicle_table.update_from_event(event)
            self.event_console.log_event(event)

        # 2. Drain and render metrics from the multiprocessing telemetry worker
        snapshot = self._controller.drain_metrics()
        if snapshot is not None:
            self.metrics_panel.update_metrics(snapshot)

        # 3. Update the slot occupancy display
        self.parking_grid.update_slots(
            self._controller.slots_snapshot(),
            self._controller.capacity,
        )

        # Reschedule next poll
        self._schedule_poll()

    def _on_start(self, config: SimulationConfig) -> None:
        try:
            self._controller.start(config)
            self.control_panel.set_running_state(True)
            self.status_badge.config(text="● EN EJECUCIÓN", fg="#a6e3a1")
            self.event_console.log_system(
                f"Simulación iniciada: {config.capacity} cupos, {config.initial_vehicles} vehículos iniciales."
            )
        except Exception as e:
            self.event_console.log_system(f"Error al iniciar simulación: {e}")

    def _on_add_vehicle(self) -> None:
        try:
            new_id = self._controller.add_vehicle()
            self.event_console.log_system(f"Vehículo #{new_id} inyectado dinámicamente a la simulación.")
        except Exception as e:
            self.event_console.log_system(f"Error al agregar vehículo: {e}")

    def _on_stop(self) -> None:
        self.event_console.log_system("Señal de parada enviada. Deteniendo hilos y telemetría...")
        self._controller.stop()
        self.control_panel.set_running_state(False)
        self.status_badge.config(text="● DETENIDO", fg="#f38ba8")
        self.event_console.log_system("Simulación detenida limpiamente.")

    def _on_reset(self) -> None:
        self._controller.reset()
        self.control_panel.set_running_state(False)
        self.status_badge.config(text="● RESTABLECIDO", fg="#f9e2af")
        self.vehicle_table.clear()
        self.event_console.clear()
        self.metrics_panel.update_metrics(MetricsSnapshot())
        self.parking_grid.update_slots(
            self._controller.slots_snapshot(),
            self._controller.capacity,
        )
        self.event_console.log_system("Simulación restablecida.")

    def _on_close(self) -> None:
        """Handle window close event gracefully."""
        if self._poll_job is not None:
            self._root.after_cancel(self._poll_job)
        self._controller.shutdown()
        self._root.destroy()
