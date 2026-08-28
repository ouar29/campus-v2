"""Fiche détaillée d'une salle : champs `.cps` bruts, gestionnaires, déplacement.

Édite directement `room.extra`, c'est-à-dire les champs `.cps` d'origine que
le modèle ne représente pas explicitement (access, equipments, roomType…).
C'est ce qui permet à `export_cps.py` de régénérer un fichier fidèle à
l'original.

`on_change` est appelé après un enregistrement ou un déplacement réussi :
l'appelant s'en sert pour rafraîchir la liste depuis laquelle la fiche a été
ouverte.
"""
from __future__ import annotations

from typing import Callable

from nicegui import ui

from model import Room


def open_room_details_dialog(app, room: Room, on_change: Callable[[], None]) -> None:
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
            on_change()
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
            on_change()
            ui.notify("Détails enregistrés")
            dialog.close()

        with ui.row().classes("justify-end w-full mt-3"):
            ui.button("Annuler", on_click=dialog.close).props("flat")
            ui.button("Enregistrer", on_click=confirm)
    dialog.open()
