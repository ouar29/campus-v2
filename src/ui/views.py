from __future__ import annotations

from nicegui import ui

from model import Building, Floor, Gestionnaire, Room
from rendering import campus_map_parts
from schema_validation import validate_campus_bytes
from campus_app import _read_uploaded_file


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

            ui.label("Gestionnaires de la salle").classes(
                "text-sm font-semibold text-gray-500 dark:text-gray-300 mt-3"
            )
            gestionnaires_options = {g.id: g.nom for g in app.controller.get_gestionnaires()}
            if not gestionnaires_options:
                ui.label(
                    "Aucun gestionnaire créé pour l'instant — utilise « Gestionnaires » dans l'en-tête."
                ).classes("text-xs text-gray-400 dark:text-gray-500")
            gestionnaires_select = ui.select(
                gestionnaires_options,
                value=list(room.gestionnaire_ids),
                label="Gestionnaires",
                multiple=True,
            ).classes("w-full").props("use-chips dense")

            ui.separator().classes("my-1")
            ui.label("Déplacer vers un autre étage").classes(
                "text-sm font-semibold text-gray-500 dark:text-gray-300"
            )
            current_building, current_floor = app.controller.find_room_location(room.id)
            with ui.row().classes("w-full gap-3"):
                move_building_select = ui.select(
                    app.controller.buildings_options(),
                    value=current_building.id if current_building else None,
                    label="Bâtiment cible",
                ).classes("flex-1")
                move_floor_select = ui.select(
                    app.controller.floors_options(current_building),
                    value=current_floor.id if current_floor else None,
                    label="Étage cible",
                ).classes("flex-1")

            def on_move_building_change(e) -> None:
                target_building = app.controller.get_building(e.value)
                move_floor_select.set_options(app.controller.floors_options(target_building))
                move_floor_select.value = target_building.floors[0].id if target_building and target_building.floors else None

            move_building_select.on_value_change(on_move_building_change)

            def do_move() -> None:
                if not move_building_select.value or not move_floor_select.value:
                    ui.notify("Choisis un bâtiment et un étage cibles", color="warning")
                    return
                try:
                    moved = app.controller.move_room(room.id, move_building_select.value, move_floor_select.value)
                except ValueError as exc:
                    ui.notify(str(exc), color="warning")
                    return
                if not moved:
                    ui.notify("La salle est déjà sur cet étage", color="warning")
                    return
                ui.notify("Salle déplacée — repositionne-la par glisser-déposer sur le plan.")
                app.room_list.refresh()
                app.render_plan_area()
                rows_view.refresh()
                dialog.close()

            with ui.row().classes("w-full justify-end"):
                ui.button("Déplacer", icon="move_down", on_click=do_move).props("outline")

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
                app.controller.assign_gestionnaires_to_room(room.id, gestionnaires_select.value or [])
                app.save()
                app.room_list.refresh()
                app.render_plan_area()
                rows_view.refresh()
                ui.notify("Détails enregistrés")
                dialog.close()

            with ui.row().classes("justify-end w-full mt-3"):
                ui.button("Annuler", on_click=dialog.close).props("flat")
                ui.button("Enregistrer", on_click=confirm)
        dialog.open()

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


def open_validation_dialog(_event=None) -> None:
    with ui.dialog() as dialog, ui.card().classes("w-[28rem]"):
        ui.label("Valider un fichier .cps").classes("text-lg font-bold")
        ui.label(
            "Dépose un fichier pour vérifier sa conformité au schema attendu, "
            "sans l'importer dans la session en cours."
        ).classes("text-sm text-gray-500")

        result_container = ui.column().classes("w-full gap-1")

        async def handle_upload(event) -> None:
            result_container.clear()
            read = await _read_uploaded_file(event)
            if read is None:
                ui.notify("Impossible de lire le fichier", type="negative")
                return

            file_name, data = read
            errors = validate_campus_bytes(data)

            with result_container:
                if not errors:
                    ui.label(f"Conforme : {file_name}").classes(
                        "text-green-600 font-medium"
                    )
                else:
                    ui.label(
                        f"{len(errors)} erreur(s) dans {file_name} :"
                    ).classes("text-red-600 font-medium")
                    with ui.scroll_area().classes("w-full h-48 border rounded p-2"):
                        for message in errors:
                            ui.label(f"- {message}").classes("text-sm")

        ui.upload(on_upload=handle_upload, auto_upload=True).props(
            "accept=.cps,.json"
        ).classes("w-full")

        with ui.row().classes("w-full justify-end"):
            ui.button("Fermer", on_click=dialog.close)

    dialog.open()


def open_gestionnaires_dialog(app) -> None:
    search = {"query": ""}

    def open_edit_dialog(gestionnaire_id: str | None) -> None:
        gestionnaire = app.controller.get_gestionnaire(gestionnaire_id) if gestionnaire_id else None

        with ui.dialog() as edit_dialog, ui.card().classes("w-96"):
            ui.label("Modifier le gestionnaire" if gestionnaire else "Nouveau gestionnaire").classes(
                "text-lg font-semibold mb-2"
            )
            nom_input = ui.input("Nom", value=gestionnaire.nom if gestionnaire else "").classes("w-full")
            email_input = ui.input("Email", value=gestionnaire.email if gestionnaire else "").classes("w-full")
            tel_input = ui.input("Téléphone", value=gestionnaire.telephone if gestionnaire else "").classes("w-full")

            def save() -> None:
                nom = (nom_input.value or "").strip()
                if not nom:
                    ui.notify("Le nom est requis", color="warning")
                    return
                if gestionnaire:
                    app.controller.update_gestionnaire(
                        gestionnaire.id,
                        nom=nom,
                        email=(email_input.value or "").strip(),
                        telephone=(tel_input.value or "").strip(),
                    )
                else:
                    app.controller.add_gestionnaire(
                        nom=nom,
                        email=(email_input.value or "").strip(),
                        telephone=(tel_input.value or "").strip(),
                    )
                edit_dialog.close()
                rows_view.refresh()

            with ui.row().classes("w-full justify-end mt-2"):
                ui.button("Annuler", on_click=edit_dialog.close).props("flat")
                ui.button("Enregistrer", on_click=save)

        edit_dialog.open()

    def confirm_delete(gestionnaire: Gestionnaire) -> None:
        rooms_using = app.controller.get_rooms_for_gestionnaire(gestionnaire.id)
        with ui.dialog() as confirm_dlg, ui.card():
            message = f"Supprimer « {gestionnaire.nom} » ?"
            if rooms_using:
                message += f" {len(rooms_using)} salle(s) perdront ce gestionnaire."
            ui.label(message)

            def do_delete() -> None:
                app.controller.delete_gestionnaire(gestionnaire.id)
                confirm_dlg.close()
                rows_view.refresh()

            with ui.row().classes("w-full justify-end mt-2"):
                ui.button("Annuler", on_click=confirm_dlg.close).props("flat")
                ui.button("Supprimer", color="negative", on_click=do_delete)
        confirm_dlg.open()

    def render_gestionnaire_row(gestionnaire: Gestionnaire) -> None:
        nb_salles = len(app.controller.get_rooms_for_gestionnaire(gestionnaire.id))
        with ui.row().classes("w-full items-center gap-3 py-1 border-b border-gray-100 dark:border-gray-700"):
            ui.label(gestionnaire.nom).classes("w-48 font-medium")
            ui.label(gestionnaire.email or "—").classes("flex-1 text-sm text-gray-600 dark:text-gray-300")
            ui.label(gestionnaire.telephone or "—").classes("w-40 text-sm text-gray-600 dark:text-gray-300")
            ui.label(f"{nb_salles} salle(s)").classes("w-28 text-sm text-gray-500 dark:text-gray-300")
            ui.button(icon="edit", on_click=lambda g=gestionnaire: open_edit_dialog(g.id)).props("flat round size=sm")
            ui.button(
                icon="delete", on_click=lambda g=gestionnaire: confirm_delete(g)
            ).props("flat round size=sm color=negative")

    @ui.refreshable
    def rows_view() -> None:
        query = search["query"].strip().lower()
        shown = False
        for gestionnaire in app.controller.get_gestionnaires():
            if query and query not in gestionnaire.nom.lower() and query not in gestionnaire.email.lower():
                continue
            shown = True
            render_gestionnaire_row(gestionnaire)
        if not shown:
            ui.label("Aucun gestionnaire ne correspond à la recherche.").classes(
                "text-gray-500 dark:text-gray-300 py-4"
            )

    def on_search_change(e) -> None:
        search["query"] = e.value or ""
        rows_view.refresh()

    with ui.dialog().props("maximized") as dialog, ui.card().classes("w-full h-full"):
        with ui.row().classes("items-center justify-between w-full mb-2"):
            ui.label("Gestionnaires de salles").classes("text-lg font-semibold")
            with ui.row().classes("items-center gap-2"):
                ui.button("+ Gestionnaire", icon="add", on_click=lambda: open_edit_dialog(None)).props(
                    "size=sm color=primary"
                )
                ui.button(icon="close", on_click=dialog.close).props("flat round")

        ui.input(
            label="Rechercher un gestionnaire (nom, email)...",
            on_change=on_search_change,
        ).classes("w-full mb-2").props("clearable dense outlined")

        with ui.scroll_area().classes("w-full h-full"):
            with ui.row().classes(
                "w-full items-center gap-3 pb-2 border-b-2 border-gray-300 dark:border-gray-600 "
                "text-sm font-semibold text-gray-500 dark:text-gray-300"
            ):
                ui.label("Nom").classes("w-48")
                ui.label("Email").classes("flex-1")
                ui.label("Téléphone").classes("w-40")
                ui.label("Salles").classes("w-28")

            rows_view()

    dialog.open()