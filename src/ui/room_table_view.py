"""Dialogue « Toutes les salles » : table transverse à tout le campus.

Aplatit la hiérarchie bâtiment → étage → salle en une seule liste, pour
retrouver une salle sans savoir où elle se trouve. `focus_room_id` ouvre la
table sur une salle précise (double-clic depuis le plan) ; dès que
l'utilisateur retouche le champ de recherche, on repasse en recherche libre.
"""
from __future__ import annotations

from nicegui import ui

from model import Building, Floor, Room
from ui.room_details_view import open_room_details_dialog


def open_room_table_dialog(app, focus_room_id: str | None = None) -> None:
    focus_room = app.controller.get_room(focus_room_id) if focus_room_id else None
    search = {
        "query": focus_room.name if focus_room else "",
        "focus_id": focus_room.id if focus_room else None,
    }

    def render_room_row(building: Building, floor: Floor, room: Room) -> None:
        def on_name_change(e) -> None:
            new_name = (e.value or "").strip()
            if not new_name:
                ui.notify("Le nom ne peut pas être vide", color="warning")
                return
            room.name = new_name
            app.save()
            app.room_list.refresh()
            app.render_plan_area()

        is_unavailable = not room.extra.get("available", True)
        row_classes = "w-full items-center gap-3 py-1 border-b border-gray-100 dark:border-gray-700"
        if is_unavailable:
            row_classes += " opacity-60"

        with ui.row().classes(row_classes):
            ui.label(building.name).classes("w-40 text-sm text-gray-600 dark:text-gray-300")
            ui.label(floor.name).classes("w-40 text-sm text-gray-600 dark:text-gray-300")
            ui.input(value=room.name, on_change=on_name_change).classes("flex-1").props("dense")
            ui.label(f"{room.capacity} pers.").classes("w-32 text-sm text-gray-600 dark:text-gray-300")
            if is_unavailable:
                ui.icon("block").classes("text-red-500 dark:text-red-400").tooltip("Indisponible")
            ui.button(
                icon="tune",
                on_click=lambda: open_room_details_dialog(app, room, rows_view.refresh),
            ).props("flat round size=sm").tooltip("Détails avancés")

    @ui.refreshable
    def rows_view() -> None:
        query = search["query"].strip().lower()
        focus_id = search["focus_id"]
        shown = False
        for building in app.campus.buildings:
            for floor in building.floors:
                for room in floor.rooms:
                    if focus_id:
                        if room.id != focus_id:
                            continue
                    elif query and query not in room.name.lower() and query not in building.name.lower() and query not in floor.name.lower():
                        continue
                    shown = True
                    render_room_row(building, floor, room)
        if not shown:
            ui.label("Aucune salle ne correspond à la recherche.").classes("text-gray-500 dark:text-gray-300 py-4")

    def on_search_change(e) -> None:
        search["query"] = e.value or ""
        search["focus_id"] = None  # dès que l'utilisateur retouche le champ, on repasse en recherche libre
        rows_view.refresh()

    with ui.dialog().props("maximized") as dialog, ui.card().classes("w-full h-full"):
        with ui.row().classes("items-center justify-between w-full mb-2"):
            ui.label("Toutes les salles").classes("text-lg font-semibold")
            ui.button(icon="close", on_click=dialog.close).props("flat round")

        has_any_room = any(floor.rooms for building in app.campus.buildings for floor in building.floors)
        if not has_any_room:
            ui.label("Aucune salle créée pour l'instant.").classes("text-gray-500 dark:text-gray-300")
        else:
            ui.input(
                label="Rechercher une salle (nom, bâtiment, étage)...",
                value=search["query"],
                on_change=on_search_change,
            ).classes("w-full mb-2").props("clearable dense outlined")

            with ui.scroll_area().classes("w-full h-full"):
                with ui.row().classes("w-full items-center gap-3 pb-2 border-b-2 border-gray-300 dark:border-gray-600 text-sm font-semibold text-gray-500 dark:text-gray-300"):
                    ui.label("Bâtiment").classes("w-40")
                    ui.label("Étage").classes("w-40")
                    ui.label("Nom de la salle").classes("flex-1")
                    ui.label("Capacité").classes("w-32")

                rows_view()

    dialog.open()
