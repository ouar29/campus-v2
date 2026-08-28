from __future__ import annotations

from nicegui import ui


def open_new_building_dialog(campus, state, save, building_select, floor_select, room_list, render_plan_area):
    with ui.dialog() as dialog, ui.card():
        ui.label("Nouveau bâtiment").classes("text-lg font-semibold")
        name_input = ui.input("Nom du bâtiment").classes("w-full")

        def confirm() -> None:
            if not name_input.value:
                ui.notify("Le nom est requis", color="warning")
                return
            from services.campus_service import CampusService
            campus_service = CampusService(campus)
            try:
                building = campus_service.create_building(name_input.value)
            except ValueError as exc:
                ui.notify(str(exc), color="warning")
                return
            save()
            state["building"] = building
            state["floor"] = None
            building_select.set_options({b.id: b.name for b in campus.buildings})
            building_select.value = building.id
            floor_select.set_options({})
            floor_select.value = None
            room_list.refresh()
            render_plan_area()
            dialog.close()

        with ui.row().classes("justify-end w-full mt-2"):
            ui.button("Annuler", on_click=dialog.close).props("flat")
            ui.button("Créer", on_click=confirm)
    dialog.open()


def open_new_floor_dialog(campus, state, save, floor_select, room_list, render_plan_area):
    if state["building"] is None:
        ui.notify("Sélectionne ou crée d'abord un bâtiment", color="warning")
        return

    building = state["building"]
    default_level = (max((f.level for f in building.floors), default=-1)) + 1
    clone_options = {"__none__": "Aucun — dessiner un nouveau contour"}
    clone_options.update({f.id: f.name for f in building.floors})

    with ui.dialog() as dialog, ui.card():
        ui.label("Nouvel étage").classes("text-lg font-semibold")
        name_input = ui.input("Nom de l'étage (ex : RDC, 1er étage, Sous-sol)").classes("w-full")
        level_input = ui.number(
            "Niveau (0 = RDC, négatif = sous-sol, positif = étage)",
            value=default_level,
            precision=0,
        ).classes("w-full")
        clone_select = ui.select(clone_options, value="__none__", label="Copier la géométrie de").classes("w-full")

        def confirm() -> None:
            if not name_input.value:
                ui.notify("Le nom est requis", color="warning")
                return
            level = int(level_input.value if level_input.value is not None else default_level)

            if clone_select.value and clone_select.value != "__none__":
                source_floor = next((f for f in building.floors if f.id == clone_select.value), None)
                if source_floor is None or not source_floor.polygon:
                    ui.notify("Impossible de copier ce contour", color="warning")
                    return
                from services.floor_service import FloorService
                try:
                    new_floor = FloorService(campus).create_floor(
                        building,
                        name_input.value,
                        [list(p) for p in source_floor.polygon],
                        level=level,
                    )
                except ValueError as exc:
                    ui.notify(str(exc), color="warning")
                    return
                save()
                state["floor"] = new_floor
                floor_select.set_options({f.id: f.name for f in building.floors})
                floor_select.value = new_floor.id
                room_list.refresh()
                render_plan_area()
                dialog.close()
                return

            state["mode"] = "drawing_floor"
            state["pending_floor_name"] = name_input.value
            state["pending_floor_level"] = level
            state["pending_points"] = []
            dialog.close()
            render_plan_area()

        with ui.row().classes("justify-end w-full mt-2"):
            ui.button("Annuler", on_click=dialog.close).props("flat")
            ui.button("Créer", on_click=confirm)
    dialog.open()


def open_new_room_dialog(state, save, room_list, render_plan_area):
    if state["floor"] is None:
        ui.notify("Sélectionne ou crée d'abord un étage", color="warning")
        return

    with ui.dialog() as dialog, ui.card():
        ui.label("Nouvelle salle").classes("text-lg font-semibold")
        name_input = ui.input("Nom de la salle").classes("w-full")
        capacity_input = ui.number("Capacité (personnes)", value=10, min=1, precision=0).classes("w-full")

        def confirm() -> None:
            if not name_input.value:
                ui.notify("Le nom est requis", color="warning")
                return
            state["mode"] = "placing_room"
            state["pending_room_name"] = name_input.value
            state["pending_room_capacity"] = int(capacity_input.value or 1)
            dialog.close()
            render_plan_area()

        with ui.row().classes("justify-end w-full mt-2"):
            ui.button("Annuler", on_click=dialog.close).props("flat")
            ui.button("Placer sur le plan", on_click=confirm)
    dialog.open()
