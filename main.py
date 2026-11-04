"""Main entry point: composes Model, Controller, and View (Composition Root)."""

import multiprocessing
import tkinter as tk

from src.config import DEFAULT_CONFIG
from src.core.app_controller import AppController
from src.views.app_window import MainWindow


def build_app() -> tuple[tk.Tk, AppController, MainWindow]:
    """Assemble the application components following the MVC architecture.

    Returns:
        A tuple of (root_window, controller, main_window).
    """
    root = tk.Tk()
    controller = AppController(config=DEFAULT_CONFIG)
    window = MainWindow(root, controller)
    return root, controller, window


def main() -> None:
    """Run the Smart Parking Simulation application."""
    root, _controller, _window = build_app()
    root.mainloop()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
