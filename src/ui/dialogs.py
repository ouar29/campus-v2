from __future__ import annotations

from nicegui import ui

from model import BUILDING_DEFAULT_SPACING
from services.campus_service import MAX_MODULAR_FLOORS


MODE_EMPTY = "empty"
MODE_MODULAR = "modular"


def _default_building_position(campus) -> list[float]:
    """Même règle que `Campus.add_building` sans position : à droite du dernier."""
    max_x = max((b.position[0] for b in campus.buildings), default=-BUILDING_DEFAULT_SPACING)
    return [max_x + BUILDING_DEFAULT_SPACING, 0.0]


def open_new_building_dialog(app) -> None:
    """Crée un bâtiment, vide (étages dessinés ensuite) ou modulaire.

    Le mode modulaire produit d'un coup un bâtiment rectangulaire dont tous
    les niveaux partagent la même géométrie — le cas courant d'un immeuble
    à plateaux identiques, qu'il serait fastidieux de dessiner étage par
    étage à la souris.
    """
    campus = app.campus
    default_position = _default_building_position(campus)

    with ui.dialog() as dialog, ui.card().classes("w-[460px] max-w-[92vw]"):
        ui.label("Nouveau bâtiment").classes("text-lg font-semibold")
        name_input = ui.input("Nom du bâtiment").classes("w-full")
        mode_toggle = ui.toggle(
            {MODE_EMPTY: "Vide", MODE_MODULAR: "Modulaire (rectangle)"},
            value=MODE_EMPTY,
        ).props("dense")
        ui.label(
            "Vide : le bâtiment est créé sans étage, à dessiner ensuite un par un. "
            "Modulaire : un rectangle répliqué à l'identique sur tous les niveaux."
        ).classes("text-xs text-gray-500 dark:text-gray-300")

        with ui.column().classes("w-full gap-2 mt-2") as modular_fields:
            ui.label("Géométrie (unités du plan, identiques aux contours d'étage)").classes(
                "text-sm font-semibold text-gray-500 dark:text-gray-300"
            )
            with ui.row().classes("w-full gap-2 no-wrap"):
                width_input = ui.number("Largeur (X)", value=20, min=0.1, step=1).props("dense outlined").classes("flex-1")
                depth_input = ui.number("Profondeur (Y)", value=10, min=0.1, step=1).props("dense outlined").classes("flex-1")
            with ui.row().classes("w-full gap-2 no-wrap"):
                count_input = ui.number("Nombre de niveaux", value=1, min=1, max=MAX_MODULAR_FLOORS, precision=0).props("dense outlined").classes("flex-1")
                lowest_input = ui.number("Niveau le plus bas", value=0, precision=0).props("dense outlined").classes("flex-1")
            ui.label("Niveau 0 = RDC, négatif = sous-sol. Les niveaux sont nommés automatiquement.").classes(
                "text-xs text-gray-500 dark:text-gray-300"
            )

            ui.label("Position sur le plan du campus (coin bas-gauche de l'empreinte)").classes(
                "text-sm font-semibold text-gray-500 dark:text-gray-300 mt-1"
            )
            with ui.row().classes("w-full gap-2 no-wrap"):
                pos_x_input = ui.number("X", value=default_position[0], step=1).props("dense outlined").classes("flex-1")
                pos_y_input = ui.number("Y", value=default_position[1], step=1).props("dense outlined").classes("flex-1")
            ui.label("Ajustable à tout moment depuis « Plan du campus ».").classes(
                "text-xs text-gray-500 dark:text-gray-300"
            )
        modular_fields.bind_visibility_from(mode_toggle, "value", value=MODE_MODULAR)

        def _number(field, fallback: float) -> float:
            try:
                return float(field.value)
            except (TypeError, ValueError):
                return fallback

        def confirm() -> None:
            if not name_input.value:
                ui.notify("Le nom est requis", color="warning")
                return
            try:
                if mode_toggle.value == MODE_MODULAR:
                    app.controller.create_modular_building(
                        name_input.value,
                        _number(width_input, 0),
                        _number(depth_input, 0),
                        floor_count=int(_number(count_input, 1)),
                        lowest_level=int(_number(lowest_input, 0)),
                        position=[_number(pos_x_input, default_position[0]), _number(pos_y_input, default_position[1])],
                    )
                else:
                    app.controller.create_building(name_input.value)
            except ValueError as exc:
                ui.notify(str(exc), color="warning")
                return
            app.refresh_campus_selection()
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
