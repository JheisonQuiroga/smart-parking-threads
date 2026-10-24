"""Parámetros globales de la simulación (capacidad, tiempos, semilla, colores, logs)."""

from typing import Optional

CAPACIDAD: int = 5
VEHICULOS_INICIALES: int = 8

# Rangos de tiempos aleatorios simulados (segundos): (mínimo, máximo)
RANGO_LLEGADA: tuple[float, float] = (0.5, 4.0)
RANGO_ESTADIA: tuple[float, float] = (3.0, 8.0)

SEMILLA: Optional[int] = None  # random.seed(); None = no reproducible

# Temporización de hilos y GUI
ACQUIRE_TIMEOUT: float = 0.5   # timeout de semaforo.acquire (s)
UI_POLL_MS: int = 100          # periodo de root.after(...) (ms)

# Persistencia
LOGS_DIR: str = "logs"

# Colores de la interfaz
COLOR_LIBRE: str = "#4caf50"
COLOR_OCUPADO: str = "#e53935"
COLOR_FONDO: str = "#1e1e2e"
