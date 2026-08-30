from __future__ import annotations

from nicegui import ui
from i18n import t
from iso_view import build_overview_parts


def open_overview_dialog(app) -> None:
    container_ref: dict = {"el": None}
    rotation_state = {"angle": 0.0}
    ROTATION_STEP = 45.0

    def redraw_overview() -> None:
        if container_ref["el"] is None:
            return
        try:
            html, js = build_overview_parts(app.campus, angle_deg=rotation_state["angle"], palette=app.palette)
        except Exception as exc:
            ui.notify(t("overview.error.render_failed", error=exc), color="negative")
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
            ui.label(t("overview.dialog.title")).classes("text-lg font-semibold")
            with ui.row().classes("items-center gap-1"):
                ui.button(icon="rotate_left", on_click=lambda: rotate(-ROTATION_STEP)) \
                    .props("flat round").tooltip(t("overview.rotate_left"))
                ui.button(icon="rotate_right", on_click=lambda: rotate(ROTATION_STEP)) \
                    .props("flat round").tooltip(t("overview.rotate_right"))
                ui.button(icon="close", on_click=dialog.close).props("flat round")
        container_ref["el"] = ui.column().classes("w-full h-full")

    dialog.open()
    redraw_overview()
