# Smart Parking Threads

Simulador de parqueadero inteligente en **Python** con interfaz gráfica en **Tkinter**, desarrollado para la asignatura *Arquitectura de Computadores y Sistemas Operativos*.

Cada **vehículo es un hilo** (`threading.Thread`) que compite por un número limitado de cupos, controlado por un **semáforo** (`Semaphore`). Las secciones críticas se protegen con un **`Lock`**, y un **proceso independiente** (`multiprocessing.Process`) calcula métricas de SO (tiempo de espera, utilización, throughput) y persiste los eventos en CSV. Así se ilustra cómo un sistema operativo planifica y bloquea procesos que comparten recursos finitos.

## Requisitos
- Python 3.10+ con `tkinter` (Ubuntu/Debian: `sudo apt-get install python3-tk`).

## Uso
```bash
python3 main.py                              # ejecutar el simulador
python3 -m unittest discover -s tests -t .   # ejecutar pruebas
```

## Arquitectura
MVC + capas de servicio y persistencia: `src/models` (M), `src/views` (V), `src/core` (C, controlador), `src/processes` (proceso de telemetría) y `src/data` (persistencia). Las reglas completas de desarrollo y de commits están en [AGENTS.md](AGENTS.md#regla-9-flujo-de-trabajo-y-convención-de-commits).

## Convenciones
- **Idioma**: código, docstrings y commits en inglés; textos de la GUI y documentación en español.
- **Desarrollo por features**: cada capa se trabaja en su rama (`feat/models`, `feat/core`, …), definiendo primero sus contratos y luego su implementación con pruebas. Ver [AGENTS.md](AGENTS.md) (secciones 10 y 11).
