"""Dialogue « Toutes les salles » : table transverse à tout le campus.

Aplatit la hiérarchie bâtiment → étage → salle en une seule liste, pour
retrouver une salle sans savoir où elle se trouve. `focus_room_id` ouvre la
table sur une salle précise (double-clic depuis le plan) ; dès que
l'utilisateur retouche le champ de recherche ou un filtre, on repasse en
navigation libre.

La recherche textuelle répond à « où est cette salle ? ». Les filtres
prédéfinis répondent à la question inverse — « quelles salles demandent mon
attention ? » — après un import massif : indisponibles, sans gestionnaire,
capacité à zéro, ou encore en attente de positionnement.
"""
from __future__ import annotations

from nicegui import ui

from i18n import t
from model import Building, Floor, Room
from services.room_service import (
    has_no_gestionnaire,
    has_suspicious_capacity,
    is_awaiting_placement,
    is_unavailable,
)
from ui.room_details_view import open_room_details_dialog

# (clé, libellé, icône, prédicat). Les prédicats vivent dans le service : ce
# sont des questions métier, la vue ne fait que les habiller.
PREDEFINED_FILTERS = (
    ("unavailable", t("room_table.filter.unavailable"), "block", lambda building, floor, room: is_unavailable(room)),
    ("no_gestionnaire", t("room_table.filter.no_gestionnaire"), "person_off", lambda building, floor, room: has_no_gestionnaire(room)),
    ("capacity", t("room_table.filter.capacity"), "error_outline", lambda building, floor, room: has_suspicious_capacity(room)),
    ("awaiting", t("room_table.filter.awaiting"), "wrong_location", lambda building, floor, room: is_awaiting_placement(building)),
)


def open_room_table_dialog(app, focus_room_id: str | None = None) -> None:
    focus_room = app.controller.get_room(focus_room_id) if focus_room_id else None
    search = {
        "query": focus_room.name if focus_room else "",
        "focus_id": focus_room.id if focus_room else None,
    }
    # Filtres cumulatifs : chacun restreint le résultat des autres.
    active_filters: set[str] = set()

    def render_room_row(building: Building, floor: Floor, room: Room) -> None:
        def on_name_change(e) -> None:
            new_name = (e.value or "").strip()
            if not new_name:
                ui.notify(t("room_table.error.empty_name"), color="warning")
                return
            room.name = new_name
            app.save()
            app.room_list.refresh()
            app.render_plan_area()

        unavailable = is_unavailable(room)
        row_classes = "w-full items-center gap-3 py-1 border-b border-gray-100 dark:border-gray-700"
        if unavailable:
            row_classes += " opacity-60"

        with ui.row().classes(row_classes):
            ui.label(building.name).classes("w-40 text-sm text-gray-600 dark:text-gray-300")
            ui.label(floor.name).classes("w-40 text-sm text-gray-600 dark:text-gray-300")
            ui.input(value=room.name, on_change=on_name_change).classes("flex-1").props("dense")
            ui.label(t("room_table.room.capacity", capacity=room.capacity)).classes("w-32 text-sm text-gray-600 dark:text-gray-300")
            if unavailable:
                ui.icon("block").classes("text-red-500 dark:text-red-400").tooltip(t("room_table.room.unavailable"))
            ui.button(
                icon="tune",
                on_click=lambda: open_room_details_dialog(app, room, rows_view.refresh),
            ).props("flat round size=sm").tooltip(t("room_table.room.details"))

    def matches_filters(building: Building, floor: Floor, room: Room) -> bool:
        return all(
            predicate(building, floor, room)
            for key, _, _, predicate in PREDEFINED_FILTERS
            if key in active_filters
        )

    @ui.refreshable
    def rows_view() -> None:
        query = search["query"].strip().lower()
        focus_id = search["focus_id"]
        rows = []
        for building in app.campus.buildings:
            for floor in building.floors:
                for room in floor.rooms:
                    if focus_id:
                        if room.id != focus_id:
                            continue
                    else:
                        if query and query not in room.name.lower() and query not in building.name.lower() and query not in floor.name.lower():
                            continue
                        if not matches_filters(building, floor, room):
                            continue
                    rows.append((building, floor, room))

        if not rows:
            ui.label(t("room_table.search.no_match")).classes("text-gray-500 dark:text-gray-300 py-4")
            return

        ui.label(t("room_table.count", count=len(rows))).classes("text-xs text-gray-500 dark:text-gray-300 py-1")
        for building, floor, room in rows:
            render_room_row(building, floor, room)

    def on_search_change(e) -> None:
        search["query"] = e.value or ""
        search["focus_id"] = None  # dès que l'utilisateur retouche le champ, on repasse en recherche libre
        rows_view.refresh()

    def make_filter_handler(key: str):
        def on_selection_change(e) -> None:
            if e.value:
                active_filters.add(key)
            else:
                active_filters.discard(key)
            # Un filtre est une nouvelle intention : on sort du mode « une
            # seule salle », sinon le filtre resterait sans effet visible.
            search["focus_id"] = None
            # La zone de filtres se redessine aussi : c'est elle qui fait
            # apparaître (ou disparaître) le bouton « Tout effacer ».
            filters_view.refresh()
            rows_view.refresh()

        return on_selection_change

    def clear_filters() -> None:
        active_filters.clear()
        search["focus_id"] = None
        filters_view.refresh()
        rows_view.refresh()

    @ui.refreshable
    def filters_view() -> None:
        with ui.row().classes("items-center gap-2 w-full mb-2"):
            ui.label(t("room_table.filters.title")).classes("text-sm font-semibold text-gray-500 dark:text-gray-300")
            for key, label, icon, _ in PREDEFINED_FILTERS:
                ui.chip(
                    label,
                    icon=icon,
                    selectable=True,
                    selected=key in active_filters,
                    on_selection_change=make_filter_handler(key),
                ).props("outline")
            if active_filters:
                ui.button(t("room_table.filters.clear"), icon="filter_alt_off", on_click=clear_filters).props("flat dense size=sm")

    with ui.dialog().props("maximized") as dialog, ui.card().classes("w-full h-full"):
        with ui.row().classes("items-center justify-between w-full mb-2"):
            ui.label(t("room_table.dialog.title")).classes("text-lg font-semibold")
            ui.button(icon="close", on_click=dialog.close).props("flat round")

        has_any_room = any(floor.rooms for building in app.campus.buildings for floor in building.floors)
        if not has_any_room:
            ui.label(t("room_table.empty")).classes("text-gray-500 dark:text-gray-300")
        else:
            ui.input(
                label=t("room_table.search"),
                value=search["query"],
                on_change=on_search_change,
            ).classes("w-full mb-2").props("clearable dense outlined")

            filters_view()

            with ui.scroll_area().classes("w-full h-full"):
                with ui.row().classes("w-full items-center gap-3 pb-2 border-b-2 border-gray-300 dark:border-gray-600 text-sm font-semibold text-gray-500 dark:text-gray-300"):
                    ui.label(t("room_table.column.building")).classes("w-40")
                    ui.label(t("room_table.column.floor")).classes("w-40")
                    ui.label(t("room_table.column.room")).classes("flex-1")
                    ui.label(t("room_table.column.capacity")).classes("w-32")

                rows_view()

    dialog.open()
