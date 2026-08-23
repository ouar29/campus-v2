from __future__ import annotations

from nicegui import ui
from iso_view import build_overview_parts


def open_overview_dialog(app) -> None:
    container_ref: dict = {"el": None}
    rotation_state = {"angle": 0.0}
    ROTATION_STEP = 45.0

    def redraw_overview() -> None:
        if container_ref["el"] is None:
            return
        try:
            html, js = build_overview_parts(app.campus, angle_deg=rotation_state["angle"])
        except Exception as exc:
            ui.notify(f"Erreur lors de la génération de la vue d'ensemble : {exc}", color="negative")
            raise
        container_ref["el"].clear()
        with container_ref["el"]:
            ui.html(html).classes("w-full h-full")
        ui.timer(0.05, lambda: ui.run_javascript(js), once=True)

    def rotate(delta_deg: float) -> None:
        rotation_state["angle"] = (rotation_state["angle"] + delta_deg) % 360
        redraw_overview()

    with ui.dialog().props("maximized") as dialog, ui.card().classes("w-full h-full"):
        with ui.row().classes("items-center justify-between w-full"):
            ui.label("Vue d'ensemble du campus").classes("text-lg font-semibold")
            with ui.row().classes("items-center gap-1"):
                ui.button(icon="rotate_left", on_click=lambda: rotate(-ROTATION_STEP)) \
                    .props("flat round").tooltip("Tourner vers la gauche (45°)")
                ui.button(icon="rotate_right", on_click=lambda: rotate(ROTATION_STEP)) \
                    .props("flat round").tooltip("Tourner vers la droite (45°)")
                ui.button(icon="close", on_click=dialog.close).props("flat round")
        container_ref["el"] = ui.column().classes("w-full h-full")

    dialog.open()
    redraw_overview()
