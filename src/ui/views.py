from __future__ import annotations

from nicegui import ui

from iso_view import build_overview_parts
from model import Building, Floor, Room
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


def open_overview_dialog(app) -> None:
    try:
        html, js = build_overview_parts(app.campus)
    except Exception as exc:
        ui.notify(f"Erreur lors de la génération de la vue d'ensemble : {exc}", color="negative")
        raise
    with ui.dialog().props("maximized") as dialog, ui.card().classes("w-full h-full"):
        with ui.row().classes("items-center justify-between w-full"):
            ui.label("Vue d'ensemble du campus").classes("text-lg font-semibold")
            ui.button(icon="close", on_click=dialog.close).props("flat round")
        ui.html(html).classes("w-full h-full")
    dialog.open()
    ui.timer(0.05, lambda: ui.run_javascript(js), once=True)


def open_room_table_dialog(app) -> None:
    search = {"query": ""}

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

        def on_capacity_change(e) -> None:
            try:
                new_capacity = int(e.value)
            except (TypeError, ValueError):
                return
            if new_capacity < 1:
                ui.notify("La capacité doit être d'au moins 1 personne", color="warning")
                return
            room.capacity = new_capacity
            app.save()
            app.room_list.refresh()
            app.render_plan_area()

        with ui.row().classes("w-full items-center gap-3 py-1 border-b border-gray-100 dark:border-gray-700"):
            ui.label(building.name).classes("w-40 text-sm text-gray-600 dark:text-gray-300")
            ui.label(floor.name).classes("w-40 text-sm text-gray-600 dark:text-gray-300")
            ui.input(value=room.name, on_change=on_name_change).classes("flex-1").props("dense")
            ui.number(value=room.capacity, min=1, precision=0, on_change=on_capacity_change).classes("w-32").props("dense")
            ui.button(icon="tune", on_click=lambda: open_room_details_dialog(app, room)).props("flat round size=sm").tooltip("Détails avancés")

    def open_room_details_dialog(app, room: Room) -> None:
        extra = room.extra

        with ui.dialog() as dialog, ui.card().classes("w-[640px] max-w-full"):
            ui.label(f"Détails avancés — {room.name}").classes("text-lg font-semibold mb-2")

            with ui.grid(columns=2).classes("w-full gap-3"):
                old_name_input = ui.input("Ancien nom (oldName)", value=extra.get("oldName", "")).props("dense")
                alt_name_input = ui.input("Nom alternatif (altName)", value=extra.get("altName", "")).props("dense")
                access_input = ui.input("Accès (access)", value=extra.get("access", "")).props("dense")
                zone_input = ui.input("Zone", value=extra.get("zone", "")).props("dense")
                booking_type_input = ui.input("Type de réservation (roomBookingType)", value=extra.get("roomBookingType", "")).props("dense")
                phone_input = ui.input("Téléphone (telephoneNumber)", value=extra.get("telephoneNumber", "")).props("dense")
                type_input = ui.input("Type", value=extra.get("type", "")).props("dense")
                room_type_input = ui.input("Type de salle (roomType)", value=extra.get("roomType", "meetingRoom")).props("dense")

            available_switch = ui.checkbox("Disponible (available)", value=bool(extra.get("available", True))).classes("mt-1")
            comment_input = ui.textarea("Commentaire", value=extra.get("comment", "")).classes("w-full")

            raw_equipments = extra.get("equipments", [])
            equipments_text = ", ".join(raw_equipments) if isinstance(raw_equipments, list) else ""
            equipments_input = ui.input(
                "Équipements (séparés par des virgules)", value=equipments_text
            ).classes("w-full")

            ui.label("Responsables de la salle (roomManagers)").classes("text-sm font-semibold text-gray-500 dark:text-gray-300 mt-3")
            managers_container = ui.column().classes("w-full gap-1")
            managers_state: list[dict] = [dict(m) for m in extra.get("roomManagers", {}).get("value", [])]

            def render_managers() -> None:
                managers_container.clear()
                with managers_container:
                    if not managers_state:
                        ui.label("Aucun responsable renseigné.").classes("text-xs text-gray-400 dark:text-gray-500")
                    for i in range(len(managers_state)):
                        with ui.row().classes("items-center gap-2 w-full"):
                            ui.input(
                                "Nom",
                                value=managers_state[i].get("name", ""),
                                on_change=lambda e, i=i: managers_state[i].update(name=e.value),
                            ).classes("flex-1").props("dense")
                            ui.input(
                                "Téléphone",
                                value=managers_state[i].get("telephoneNumber", ""),
                                on_change=lambda e, i=i: managers_state[i].update(telephoneNumber=e.value),
                            ).classes("flex-1").props("dense")
                            ui.input(
                                "Email",
                                value=managers_state[i].get("email", ""),
                                on_change=lambda e, i=i: managers_state[i].update(email=e.value),
                            ).classes("flex-1").props("dense")
                            ui.button(icon="delete", on_click=lambda i=i: remove_manager(i)).props("flat round size=sm")

            def remove_manager(i: int) -> None:
                managers_state.pop(i)
                render_managers()

            def add_manager() -> None:
                managers_state.append({"name": "", "telephoneNumber": "", "email": ""})
                render_managers()

            render_managers()
            ui.button("+ Responsable", on_click=add_manager).props("size=sm outline").classes("mt-1")

            def confirm() -> None:
                extra["oldName"] = old_name_input.value or ""
                extra["altName"] = alt_name_input.value or ""
                extra["access"] = access_input.value or ""
                extra["zone"] = zone_input.value or ""
                extra["roomBookingType"] = booking_type_input.value or ""
                extra["telephoneNumber"] = phone_input.value or ""
                extra["type"] = type_input.value or ""
                extra["roomType"] = room_type_input.value or "meetingRoom"
                extra["available"] = bool(available_switch.value)
                extra["comment"] = comment_input.value or ""
                extra["equipments"] = [s.strip() for s in (equipments_input.value or "").split(",") if s.strip()]
                extra["roomManagers"] = {
                    "value": [
                        m for m in managers_state
                        if (m.get("name") or m.get("telephoneNumber") or m.get("email"))
                    ]
                }
                app.save()
                ui.notify("Détails enregistrés")
                dialog.close()

            with ui.row().classes("justify-end w-full mt-3"):
                ui.button("Annuler", on_click=dialog.close).props("flat")
                ui.button("Enregistrer", on_click=confirm)
        dialog.open()

    @ui.refreshable
    def rows_view() -> None:
        query = search["query"].strip().lower()
        shown = False
        for building in app.campus.buildings:
            for floor in building.floors:
                for room in floor.rooms:
                    if query and query not in room.name.lower() and query not in building.name.lower() and query not in floor.name.lower():
                        continue
                    shown = True
                    render_room_row(building, floor, room)
        if not shown:
            ui.label("Aucune salle ne correspond à la recherche.").classes("text-gray-500 dark:text-gray-300 py-4")

    def on_search_change(e) -> None:
        search["query"] = e.value or ""
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
