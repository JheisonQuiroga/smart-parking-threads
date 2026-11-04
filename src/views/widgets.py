"""Reusable visual widgets for the Smart Parking simulator (Tkinter).

All presentation logic lives here. Widgets never communicate directly with
threads or sync primitives; they only render models and dispatch user actions.
"""

import base64
import io
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from PIL import Image

from src.config import SimulationConfig
from src.models.events import VehicleEvent
from src.models.metrics import MetricsSnapshot
from src.models.vehicle import VehicleInfo, VehicleState

ASSETS_DIR = Path(__file__).resolve().parent / "assets"

# Presentation dictionary mapping internal VehicleState to Spanish GUI labels
STATE_LABELS: dict[VehicleState, str] = {
    VehicleState.ARRIVING: "Llegando (Nuevo)",
    VehicleState.WAITING: "Esperando cupo (Bloqueado)",
    VehicleState.PARKED: "Estacionado (En ejecución)",
    VehicleState.EXITED: "Salió (Terminado)",
}

STATE_COLORS: dict[VehicleState, str] = {
    VehicleState.ARRIVING: "#89dceb",
    VehicleState.WAITING: "#f9e2af",
    VehicleState.PARKED: "#a6e3a1",
    VehicleState.EXITED: "#6c7086",
}


class IconHelper:
    """Loads and resizes PNG icon assets with transparent backgrounds."""

    _cache: dict[tuple[int, str, int, int], tk.PhotoImage] = {}

    @classmethod
    def get_icon(
        cls,
        filename: str,
        width: int = 56,
        height: int = 56,
        master: Optional[tk.Widget] = None,
    ) -> Optional[tk.PhotoImage]:
        """Return a cached Tkinter PhotoImage for the specified asset and master window."""
        root = master.winfo_toplevel() if master is not None else None
        root_id = id(root) if root is not None else 0
        key = (root_id, filename, width, height)
        if key in cls._cache:
            return cls._cache[key]

        filepath = ASSETS_DIR / filename
        if not filepath.exists():
            return None

        try:
            pil_image = Image.open(filepath).convert("RGBA")
            pil_image = pil_image.resize((width, height), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            pil_image.save(buffer, format="PNG")
            base64_data = base64.b64encode(buffer.getvalue()).decode("ascii")
            photo = tk.PhotoImage(data=base64_data, master=root)
            cls._cache[key] = photo
            return photo
        except Exception:
            # Fallback to direct PhotoImage if PIL fails
            try:
                raw = tk.PhotoImage(file=str(filepath), master=root)
                sub_x = max(1, raw.width() // width)
                sub_y = max(1, raw.height() // height)
                subsampled = raw.subsample(sub_x, sub_y)
                cls._cache[key] = subsampled
                return subsampled
            except Exception:
                return None


class ControlPanel(tk.LabelFrame):
    """Configuration fields and control buttons for the simulator."""

    def __init__(
        self,
        master: tk.Widget,
        default_config: SimulationConfig,
        on_start: Callable[[SimulationConfig], None],
        on_add: Callable[[], None],
        on_stop: Callable[[], None],
        on_reset: Callable[[], None],
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            text=" Configuración y Controles ",
            font=("Segoe UI", 10, "bold"),
            fg="#cdd6f4",
            bg="#252538",
            bd=1,
            relief="solid",
            **kwargs,
        )
        self._default_config = default_config
        self._on_start = on_start
        self._on_add = on_add
        self._on_stop = on_stop
        self._on_reset = on_reset

        self._build_fields()
        self._build_buttons()
        self.set_running_state(False)

    def _build_fields(self) -> None:
        fields_frame = tk.Frame(self, bg="#252538")
        fields_frame.pack(fill="x", padx=10, pady=8)

        # Row 0: Capacidad y Vehículos iniciales
        tk.Label(fields_frame, text="Capacidad (cupos):", fg="#a6adc8", bg="#252538", font=("Segoe UI", 9)).grid(
            row=0, column=0, sticky="w", padx=4, pady=3
        )
        self.entry_capacity = tk.Spinbox(
            fields_frame, from_=1, to=20, width=6, bg="#181825", fg="#ffffff",
            insertbackground="#ffffff", bd=1, relief="solid"
        )
        self.entry_capacity.delete(0, "end")
        self.entry_capacity.insert(0, str(self._default_config.capacity))
        self.entry_capacity.grid(row=0, column=1, sticky="w", padx=4, pady=3)

        tk.Label(fields_frame, text="Vehículos iniciales:", fg="#a6adc8", bg="#252538", font=("Segoe UI", 9)).grid(
            row=0, column=2, sticky="w", padx=(12, 4), pady=3
        )
        self.entry_initial = tk.Spinbox(
            fields_frame, from_=0, to=50, width=6, bg="#181825", fg="#ffffff",
            insertbackground="#ffffff", bd=1, relief="solid"
        )
        self.entry_initial.delete(0, "end")
        self.entry_initial.insert(0, str(self._default_config.initial_vehicles))
        self.entry_initial.grid(row=0, column=3, sticky="w", padx=4, pady=3)

        # Row 1: Tiempos de llegada y estadía
        tk.Label(fields_frame, text="Llegada mín/máx (s):", fg="#a6adc8", bg="#252538", font=("Segoe UI", 9)).grid(
            row=1, column=0, sticky="w", padx=4, pady=3
        )
        arrival_box = tk.Frame(fields_frame, bg="#252538")
        arrival_box.grid(row=1, column=1, sticky="w", padx=4, pady=3)
        self.entry_arr_min = tk.Entry(arrival_box, width=4, bg="#181825", fg="#ffffff", insertbackground="#ffffff", bd=1)
        self.entry_arr_min.insert(0, str(self._default_config.arrival_time_range[0]))
        self.entry_arr_min.pack(side="left")
        tk.Label(arrival_box, text="-", fg="#a6adc8", bg="#252538").pack(side="left")
        self.entry_arr_max = tk.Entry(arrival_box, width=4, bg="#181825", fg="#ffffff", insertbackground="#ffffff", bd=1)
        self.entry_arr_max.insert(0, str(self._default_config.arrival_time_range[1]))
        self.entry_arr_max.pack(side="left")

        tk.Label(fields_frame, text="Estadía mín/máx (s):", fg="#a6adc8", bg="#252538", font=("Segoe UI", 9)).grid(
            row=1, column=2, sticky="w", padx=(12, 4), pady=3
        )
        park_box = tk.Frame(fields_frame, bg="#252538")
        park_box.grid(row=1, column=3, sticky="w", padx=4, pady=3)
        self.entry_park_min = tk.Entry(park_box, width=4, bg="#181825", fg="#ffffff", insertbackground="#ffffff", bd=1)
        self.entry_park_min.insert(0, str(self._default_config.parking_time_range[0]))
        self.entry_park_min.pack(side="left")
        tk.Label(park_box, text="-", fg="#a6adc8", bg="#252538").pack(side="left")
        self.entry_park_max = tk.Entry(park_box, width=4, bg="#181825", fg="#ffffff", insertbackground="#ffffff", bd=1)
        self.entry_park_max.insert(0, str(self._default_config.parking_time_range[1]))
        self.entry_park_max.pack(side="left")

        # Row 2: Semilla opcional
        tk.Label(fields_frame, text="Semilla (seed opcional):", fg="#a6adc8", bg="#252538", font=("Segoe UI", 9)).grid(
            row=2, column=0, sticky="w", padx=4, pady=3
        )
        self.entry_seed = tk.Entry(fields_frame, width=10, bg="#181825", fg="#ffffff", insertbackground="#ffffff", bd=1)
        self.entry_seed.grid(row=2, column=1, sticky="w", padx=4, pady=3)

    def _build_buttons(self) -> None:
        btn_frame = tk.Frame(self, bg="#252538")
        btn_frame.pack(fill="x", padx=10, pady=(4, 10))

        self.btn_start = tk.Button(
            btn_frame,
            text="▶ Iniciar simulación",
            bg="#2e5b32",
            fg="#ffffff",
            activebackground="#3e7b42",
            activeforeground="#ffffff",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
            command=self._handle_start,
        )
        self.btn_start.pack(side="left", padx=4)

        self.btn_add = tk.Button(
            btn_frame,
            text="➕ Agregar vehículo",
            bg="#1e3a5f",
            fg="#ffffff",
            activebackground="#2b5285",
            activeforeground="#ffffff",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
            command=self._on_add,
        )
        self.btn_add.pack(side="left", padx=4)

        self.btn_stop = tk.Button(
            btn_frame,
            text="⏹ Detener",
            bg="#6b2c34",
            fg="#ffffff",
            activebackground="#8f3b46",
            activeforeground="#ffffff",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
            command=self._on_stop,
        )
        self.btn_stop.pack(side="left", padx=4)

        self.btn_reset = tk.Button(
            btn_frame,
            text="🔄 Reiniciar",
            bg="#6e4c1f",
            fg="#ffffff",
            activebackground="#96682b",
            activeforeground="#ffffff",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
            command=self._on_reset,
        )
        self.btn_reset.pack(side="left", padx=4)

    def _handle_start(self) -> None:
        config = self.get_config()
        if config is not None:
            self._on_start(config)

    def get_config(self) -> Optional[SimulationConfig]:
        """Parse, validate and return SimulationConfig from inputs."""
        try:
            cap = int(self.entry_capacity.get())
            init = int(self.entry_initial.get())
            arr_min = float(self.entry_arr_min.get())
            arr_max = float(self.entry_arr_max.get())
            park_min = float(self.entry_park_min.get())
            park_max = float(self.entry_park_max.get())
            seed_val = self.entry_seed.get().strip()
            seed = int(seed_val) if seed_val else None

            return SimulationConfig(
                capacity=cap,
                initial_vehicles=init,
                arrival_time_range=(arr_min, arr_max),
                parking_time_range=(park_min, park_max),
                seed=seed,
            )
        except Exception as e:
            tk.messagebox.showerror("Error de configuración", f"Valores de configuración inválidos:\n{e}")
            return None

    def set_running_state(self, is_running: bool) -> None:
        """Toggle buttons and entries depending on active simulation state."""
        state_entries = "disabled" if is_running else "normal"
        self.entry_capacity.config(state=state_entries)
        self.entry_initial.config(state=state_entries)
        self.entry_arr_min.config(state=state_entries)
        self.entry_arr_max.config(state=state_entries)
        self.entry_park_min.config(state=state_entries)
        self.entry_park_max.config(state=state_entries)
        self.entry_seed.config(state=state_entries)

        self.btn_start.config(state="disabled" if is_running else "normal")
        self.btn_add.config(state="normal" if is_running else "disabled")
        self.btn_stop.config(state="normal" if is_running else "disabled")
        self.btn_reset.config(state="normal" if not is_running else "disabled")


class ParkingGrid(tk.LabelFrame):
    """Visual parking lot grid displaying every bay with live status and icons."""

    def __init__(self, master: tk.Widget, **kwargs) -> None:
        super().__init__(
            master,
            text=" Plazas de Parqueo (Recursos Finitos del SO) ",
            font=("Segoe UI", 10, "bold"),
            fg="#cdd6f4",
            bg="#252538",
            bd=1,
            relief="solid",
            **kwargs,
        )
        self._car_icon = IconHelper.get_icon("car.png", 52, 52, master=self)
        self._parking_icon = IconHelper.get_icon("parking.png", 52, 52, master=self)

        self._summary_label = tk.Label(
            self,
            text="Ocupación: 0 / 0 (0% utiliz.)",
            font=("Segoe UI", 9, "bold"),
            fg="#cdd6f4",
            bg="#252538",
        )
        self._summary_label.pack(anchor="w", padx=10, pady=(6, 2))

        # Canvas for the occupancy progress bar
        self._progress_canvas = tk.Canvas(self, height=8, bg="#181825", highlightthickness=0)
        self._progress_canvas.pack(fill="x", padx=10, pady=(0, 8))

        # Grid container for slot cards
        self._cards_container = tk.Frame(self, bg="#252538")
        self._cards_container.pack(fill="both", expand=True, padx=8, pady=4)

        self._slot_cards: list[dict[str, tk.Widget]] = []
        self._current_capacity = 0

    def update_slots(self, slots: tuple[Optional[int], ...], capacity: int) -> None:
        """Update slot occupancy, icons, and badges."""
        if capacity != self._current_capacity:
            self._rebuild_cards(capacity)

        occupied_count = sum(1 for v in slots if v is not None)
        pct = (occupied_count / capacity * 100) if capacity > 0 else 0.0

        self._summary_label.config(
            text=f"Ocupación: {occupied_count} / {capacity} cajones  |  Libres: {capacity - occupied_count}  |  {pct:.1f}%"
        )

        # Draw progress bar
        self._progress_canvas.delete("all")
        width = self._progress_canvas.winfo_width()
        if width > 1:
            bar_w = int(width * (occupied_count / capacity))
            color = "#f38ba8" if pct >= 80 else ("#f9e2af" if pct >= 50 else "#a6e3a1")
            self._progress_canvas.create_rectangle(0, 0, bar_w, 8, fill=color, outline="")

        # Update each card
        for i, occupant in enumerate(slots):
            if i >= len(self._slot_cards):
                break
            card = self._slot_cards[i]
            if occupant is None:
                # Slot is free
                card["frame"].config(bg="#1a2e1d", highlightbackground="#2e5b32")
                card["title"].config(bg="#1a2e1d", fg="#a6e3a1")
                card["icon_label"].config(bg="#1a2e1d", image=self._parking_icon or "")
                card["status_label"].config(bg="#1a2e1d", text="DISPONIBLE", fg="#a6e3a1")
            else:
                # Slot is occupied by vehicle
                card["frame"].config(bg="#3a1c24", highlightbackground="#8f3b46")
                card["title"].config(bg="#3a1c24", fg="#f38ba8")
                card["icon_label"].config(bg="#3a1c24", image=self._car_icon or "")
                card["status_label"].config(
                    bg="#3a1c24", text=f"Vehículo #{occupant}", fg="#ffffff"
                )

    def _rebuild_cards(self, capacity: int) -> None:
        for card in self._slot_cards:
            card["frame"].destroy()
        self._slot_cards.clear()
        self._current_capacity = capacity

        columns = min(5, max(1, capacity))
        for i in range(capacity):
            row = i // columns
            col = i % columns

            card_frame = tk.Frame(
                self._cards_container,
                bg="#181825",
                highlightthickness=1,
                highlightbackground="#313244",
                padx=8,
                pady=6,
            )
            card_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            self._cards_container.grid_columnconfigure(col, weight=1)

            title = tk.Label(
                card_frame,
                text=f"Cajón #{i + 1}",
                font=("Segoe UI", 9, "bold"),
                fg="#cdd6f4",
                bg="#181825",
            )
            title.pack(anchor="center")

            icon_label = tk.Label(card_frame, bg="#181825", image=self._parking_icon or "")
            icon_label.pack(pady=4)

            status_label = tk.Label(
                card_frame,
                text="DISPONIBLE",
                font=("Segoe UI", 8, "bold"),
                fg="#a6e3a1",
                bg="#181825",
            )
            status_label.pack()

            self._slot_cards.append(
                {
                    "frame": card_frame,
                    "title": title,
                    "icon_label": icon_label,
                    "status_label": status_label,
                }
            )


class MetricsPanel(tk.LabelFrame):
    """Dashboard displaying real-time OS scheduling KPIs calculated by multiprocessing."""

    def __init__(self, master: tk.Widget, **kwargs) -> None:
        super().__init__(
            master,
            text=" Métricas de Rendimiento del SO (Multiprocessing) ",
            font=("Segoe UI", 10, "bold"),
            fg="#cdd6f4",
            bg="#252538",
            bd=1,
            relief="solid",
            **kwargs,
        )
        self._cards: dict[str, tk.Label] = {}
        self._build_dashboard()

    def _build_dashboard(self) -> None:
        container = tk.Frame(self, bg="#252538")
        container.pack(fill="x", padx=8, pady=8)

        kpis = [
            ("wait_time", "T. Espera Prom.", "0.00 s", "#f9e2af"),
            ("service_time", "T. Servicio Prom.", "0.00 s", "#89dceb"),
            ("turnaround", "T. Retorno Prom.", "0.00 s", "#cba6f7"),
            ("utilization", "Utilización Recurso", "0.0 %", "#a6e3a1"),
            ("throughput", "Tasa Atención", "0.00 v/min", "#89b4fa"),
            ("served", "Atendidos (Fin)", "0", "#a6e3a1"),
            ("waiting", "En Cola (Bloqueados)", "0", "#f38ba8"),
        ]

        for i, (key, label, default, color) in enumerate(kpis):
            col = i % 4
            row = i // 4

            card = tk.Frame(container, bg="#181825", bd=1, relief="solid", padx=6, pady=4)
            card.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
            container.grid_columnconfigure(col, weight=1)

            tk.Label(card, text=label, font=("Segoe UI", 8), fg="#a6adc8", bg="#181825").pack()
            val_lbl = tk.Label(
                card, text=default, font=("Segoe UI", 11, "bold"), fg=color, bg="#181825"
            )
            val_lbl.pack()
            self._cards[key] = val_lbl

    def update_metrics(self, snapshot: Optional[MetricsSnapshot]) -> None:
        """Update KPI values from the latest snapshot."""
        if snapshot is None:
            return

        self._cards["wait_time"].config(text=f"{snapshot.average_waiting_time_s:.2f} s")
        self._cards["service_time"].config(text=f"{snapshot.average_service_time_s:.2f} s")
        self._cards["turnaround"].config(text=f"{snapshot.average_turnaround_time_s:.2f} s")
        self._cards["utilization"].config(text=f"{snapshot.utilization_percent:.1f} %")
        self._cards["throughput"].config(text=f"{snapshot.throughput_per_minute:.2f} v/min")
        self._cards["served"].config(text=str(snapshot.served_vehicles))
        self._cards["waiting"].config(text=str(snapshot.waiting_vehicles))


class VehicleTable(tk.LabelFrame):
    """Table showing live vehicle threads, their OS state, and accumulated times."""

    def __init__(self, master: tk.Widget, **kwargs) -> None:
        super().__init__(
            master,
            text=" Hilos de Ejecución (Vehículos / Procesos Concurrentes) ",
            font=("Segoe UI", 10, "bold"),
            fg="#cdd6f4",
            bg="#252538",
            bd=1,
            relief="solid",
            **kwargs,
        )
        self._vehicles: dict[int, VehicleInfo] = {}
        self._timestamps: dict[int, dict[str, float]] = {}
        self._build_tree()

    def _build_tree(self) -> None:
        tree_frame = tk.Frame(self, bg="#252538")
        tree_frame.pack(fill="both", expand=True, padx=8, pady=8)

        columns = ("id", "state", "slot", "waiting", "parking", "turnaround")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=8)

        self.tree.heading("id", text="ID Hilo")
        self.tree.heading("state", text="Estado del Proceso (SO)")
        self.tree.heading("slot", text="Cajón")
        self.tree.heading("waiting", text="T. Espera")
        self.tree.heading("parking", text="T. Servicio")
        self.tree.heading("turnaround", text="T. Retorno")

        self.tree.column("id", width=70, anchor="center")
        self.tree.column("state", width=190, anchor="w")
        self.tree.column("slot", width=70, anchor="center")
        self.tree.column("waiting", width=85, anchor="e")
        self.tree.column("parking", width=85, anchor="e")
        self.tree.column("turnaround", width=85, anchor="e")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Tags for colors
        for state, color in STATE_COLORS.items():
            self.tree.tag_configure(state.value, foreground=color)

    def update_from_event(self, event: VehicleEvent) -> None:
        """Update or insert vehicle entry based on a new VehicleEvent."""
        import time as _time

        v_id = event.vehicle_id
        if v_id not in self._vehicles:
            self._vehicles[v_id] = VehicleInfo(
                vehicle_id=v_id,
                state=event.state,
                slot=event.slot,
            )
            self._timestamps[v_id] = {}

        info = self._vehicles[v_id]
        ts = self._timestamps[v_id]
        info.state = event.state
        if event.slot is not None:
            info.slot = event.slot

        # Track state transitions and accumulate elapsed times
        now = event.timestamp if event.timestamp > 0 else _time.time()
        if event.state == VehicleState.WAITING:
            if "waiting_start" not in ts:
                ts["waiting_start"] = now
        elif event.state == VehicleState.PARKED:
            if "parked_start" not in ts:
                ts["parked_start"] = now
            if "waiting_start" in ts and info.waiting_time_s == 0.0:
                info.waiting_time_s = max(0.0, now - ts["waiting_start"])
        elif event.state == VehicleState.EXITED:
            if "parked_start" in ts and info.parking_time_s == 0.0:
                info.parking_time_s = max(0.0, now - ts["parked_start"])

        # Also accept any direct metrics emitted with the event
        if event.waiting_time_s > 0:
            info.waiting_time_s = event.waiting_time_s
        if event.parking_time_s > 0:
            info.parking_time_s = event.parking_time_s

        self._render_row(v_id)

    def refresh_live_times(self) -> None:
        """Update dynamically ticking times for all currently waiting and parked vehicles."""
        import time as _time

        now = _time.time()
        for v_id, info in self._vehicles.items():
            ts = self._timestamps.get(v_id, {})
            if info.state == VehicleState.WAITING and "waiting_start" in ts:
                live_wait = max(0.0, now - ts["waiting_start"])
                self._render_row(v_id, live_waiting=live_wait)
            elif info.state == VehicleState.PARKED and "parked_start" in ts:
                live_park = max(0.0, now - ts["parked_start"])
                self._render_row(v_id, live_parking=live_park)

    def _render_row(
        self,
        vehicle_id: int,
        live_waiting: Optional[float] = None,
        live_parking: Optional[float] = None,
    ) -> None:
        """Format and update the Treeview row for the given vehicle."""
        info = self._vehicles[vehicle_id]
        slot_str = f"#{info.slot + 1}" if info.slot is not None else "—"
        state_label = STATE_LABELS.get(info.state, info.state.value)

        wait_s = live_waiting if live_waiting is not None else info.waiting_time_s
        park_s = live_parking if live_parking is not None else info.parking_time_s
        turnaround_s = wait_s + park_s

        row_values = (
            f"Vehículo #{info.vehicle_id}",
            state_label,
            slot_str,
            f"{wait_s:.2f} s",
            f"{park_s:.2f} s",
            f"{turnaround_s:.2f} s",
        )

        item_id = str(vehicle_id)
        if self.tree.exists(item_id):
            self.tree.item(item_id, values=row_values, tags=(info.state.value,))
        else:
            self.tree.insert("", "end", iid=item_id, values=row_values, tags=(info.state.value,))

    def clear(self) -> None:
        """Clear all vehicle rows and time records."""
        self._vehicles.clear()
        self._timestamps.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)


class EventConsole(tk.LabelFrame):
    """Terminal-like scrolled console displaying critical section and sync events."""

    def __init__(self, master: tk.Widget, **kwargs) -> None:
        super().__init__(
            master,
            text=" Bitácora de Sincronización SO (Sección Crítica y Semáforos) ",
            font=("Segoe UI", 10, "bold"),
            fg="#cdd6f4",
            bg="#252538",
            bd=1,
            relief="solid",
            **kwargs,
        )
        self._build_console()

    def _build_console(self) -> None:
        container = tk.Frame(self, bg="#252538")
        container.pack(fill="both", expand=True, padx=8, pady=8)

        self.text_area = tk.Text(
            container,
            height=7,
            bg="#181825",
            fg="#cdd6f4",
            font=("Consolas", 9),
            insertbackground="#ffffff",
            bd=0,
            highlightthickness=1,
            highlightbackground="#313244",
            wrap="word",
        )
        scroll = ttk.Scrollbar(container, orient="vertical", command=self.text_area.yview)
        self.text_area.configure(yscrollcommand=scroll.set)

        self.text_area.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # Color tags
        self.text_area.tag_configure("time", foreground="#6c7086")
        self.text_area.tag_configure("arriving", foreground="#89dceb")
        self.text_area.tag_configure("waiting", foreground="#f9e2af")
        self.text_area.tag_configure("parked", foreground="#a6e3a1", font=("Consolas", 9, "bold"))
        self.text_area.tag_configure("exited", foreground="#f38ba8")
        self.text_area.tag_configure("system", foreground="#cba6f7")

    def log_event(self, event: VehicleEvent) -> None:
        """Format and append a VehicleEvent to the console."""
        from datetime import datetime

        time_str = datetime.fromtimestamp(event.timestamp).strftime("%H:%M:%S")

        action_text = ""
        tag = event.state.value

        if event.state == VehicleState.ARRIVING:
            action_text = f"Vehículo #{event.vehicle_id} llegó (Nuevo)"
        elif event.state == VehicleState.WAITING:
            action_text = (
                f"Vehículo #{event.vehicle_id} solicita recurso -> Bloqueado en Semáforo (Cola)"
            )
        elif event.state == VehicleState.PARKED:
            slot_str = f"Cajón #{event.slot + 1}" if event.slot is not None else "cajón"
            action_text = (
                f"Vehículo #{event.vehicle_id} adquirió Semáforo -> Lock tomado -> "
                f"Ocupa {slot_str} [Ocupados: {event.occupied}/{event.capacity}]"
            )
        elif event.state == VehicleState.EXITED:
            slot_str = f"Cajón #{event.slot + 1}" if event.slot is not None else "cajón"
            action_text = (
                f"Vehículo #{event.vehicle_id} Lock tomado -> Libera {slot_str} -> "
                f"Semáforo liberado [Ocupados: {event.occupied}/{event.capacity}]"
            )

        self.text_area.insert("end", f"[{time_str}] ", "time")
        self.text_area.insert("end", f"{action_text}\n", tag)
        self.text_area.see("end")

    def log_system(self, message: str) -> None:
        """Log a generic system information message."""
        from datetime import datetime

        time_str = datetime.now().strftime("%H:%M:%S")
        self.text_area.insert("end", f"[{time_str}] [SISTEMA] ", "time")
        self.text_area.insert("end", f"{message}\n", "system")
        self.text_area.see("end")

    def clear(self) -> None:
        """Clear all console output."""
        self.text_area.delete("1.0", "end")
