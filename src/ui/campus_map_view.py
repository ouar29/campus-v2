"""Dialogue « Plan du campus » : positionnement des bâtiments.

Vue du dessus à l'échelle réelle (lecture seule) doublée d'une table des
coordonnées X/Y, seul endroit où la position d'un bâtiment se modifie.
"""
from __future__ import annotations

from nicegui import ui

from model import Building
from rendering import campus_map_parts


def open_campus_map_dialog(app) -> None:
    container_ref: dict = {"el": None}
    search = {"query": ""}

    def redraw_map() -> None:
        if container_ref["el"] is None:
            return
        container_ref["el"].clear()
        html, js = campus_map_parts(app.campus)
        with container_ref["el"]:
            ui.html(html).classes("w-full h-full")
        ui.timer(0.05, lambda: ui.run_javascript(js), once=True)

    def make_position_handlers(building: Building):
        def on_x_change(e) -> None:
            try:
                building.position[0] = float(e.value)
            except (TypeError, ValueError):
                return
            app.save()
            redraw_map()

        def on_y_change(e) -> None:
            try:
                building.position[1] = float(e.value)
            except (TypeError, ValueError):
                return
            app.save()
            redraw_map()

        return on_x_change, on_y_change

    def render_building_position_row(building: Building) -> None:
        on_x_change, on_y_change = make_position_handlers(building)
        with ui.row().classes("w-full items-center gap-3 py-1 border-b border-gray-100 dark:border-gray-700"):
            ui.label(building.name).classes("flex-1 font-medium")
            ui.number(label="X", value=building.position[0], step=1, on_change=on_x_change).props("dense outlined").classes("w-32")
            ui.number(label="Y", value=building.position[1], step=1, on_change=on_y_change).props("dense outlined").classes("w-32")

    @ui.refreshable
    def rows_view() -> None:
        query = search["query"].strip().lower()
        shown = False
        for building in app.campus.buildings:
            if query and query not in building.name.lower():
                continue
            shown = True
            render_building_position_row(building)
        if not shown:
            ui.label("Aucun bâtiment ne correspond à la recherche.").classes("text-gray-500 dark:text-gray-300 py-4")

    def on_search_change(e) -> None:
        search["query"] = e.value or ""
        rows_view.refresh()

    with ui.dialog().props("maximized") as dialog, ui.card().classes("w-full h-full"):
        with ui.row().classes("items-center justify-between w-full mb-2"):
            ui.label("Plan du campus").classes("text-lg font-semibold")
            ui.button(icon="close", on_click=dialog.close).props("flat round")

        if not app.campus.buildings:
            ui.label("Aucun bâtiment à positionner. Crée d'abord un bâtiment.").classes("text-gray-500 dark:text-gray-300")
        else:
            ui.label("Vérification visuelle (lecture seule)").classes("text-xs text-gray-500 dark:text-gray-300 mb-1")
            with ui.element("div").style("width: 100%; height: 40vh;"):
                container_ref["el"] = ui.column().classes("w-full h-full")

            ui.separator().classes("my-3")

            ui.label(
                "Table des positions (coordonnées réelles, mêmes unités que les contours d'étage) "
                "— modifie X/Y ici."
            ).classes("text-xs text-gray-500 dark:text-gray-300 mb-1")
            ui.input(
                label="Rechercher un bâtiment...",
                on_change=on_search_change,
            ).classes("w-full mb-2").props("clearable dense outlined")

            with ui.row().classes("w-full items-center gap-3 pb-2 border-b-2 border-gray-300 dark:border-gray-600 text-sm font-semibold text-gray-500 dark:text-gray-300"):
                ui.label("Bâtiment").classes("flex-1")
                ui.label("X").classes("w-32")
                ui.label("Y").classes("w-32")

            rows_view()
            redraw_map()

    dialog.open()
