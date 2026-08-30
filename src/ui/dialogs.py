from __future__ import annotations

from nicegui import ui

from i18n import t
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
        ui.label(t("building.dialog.title")).classes("text-lg font-semibold")
        name_input = ui.input(t("building.dialog.name")).classes("w-full")
        mode_toggle = ui.toggle(
            {MODE_EMPTY: t("building.mode.empty"), MODE_MODULAR: t("building.mode.modular")},
            value=MODE_EMPTY,
        ).props("dense")
        ui.label(t("building.mode.hint")).classes("text-xs text-gray-500 dark:text-gray-300")

        with ui.column().classes("w-full gap-2 mt-2") as modular_fields:
            ui.label(t("building.modular.geometry_title")).classes(
                "text-sm font-semibold text-gray-500 dark:text-gray-300"
            )
            with ui.row().classes("w-full gap-2 no-wrap"):
                width_input = ui.number(t("building.modular.width"), value=20, min=0.1, step=1).props("dense outlined").classes("flex-1")
                depth_input = ui.number(t("building.modular.depth"), value=10, min=0.1, step=1).props("dense outlined").classes("flex-1")
            with ui.row().classes("w-full gap-2 no-wrap"):
                count_input = ui.number(t("building.modular.floor_count"), value=1, min=1, max=MAX_MODULAR_FLOORS, precision=0).props("dense outlined").classes("flex-1")
                lowest_input = ui.number(t("building.modular.lowest_level"), value=0, precision=0).props("dense outlined").classes("flex-1")
            ui.label(t("building.modular.level_hint")).classes(
                "text-xs text-gray-500 dark:text-gray-300"
            )

            ui.label(t("building.modular.position_title")).classes(
                "text-sm font-semibold text-gray-500 dark:text-gray-300 mt-1"
            )
            with ui.row().classes("w-full gap-2 no-wrap"):
                pos_x_input = ui.number(t("campus_map.column.x"), value=default_position[0], step=1).props("dense outlined").classes("flex-1")
                pos_y_input = ui.number(t("campus_map.column.y"), value=default_position[1], step=1).props("dense outlined").classes("flex-1")
            ui.label(t("building.modular.position_hint")).classes(
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
                ui.notify(t("common.name_required"), color="warning")
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
            ui.button(t("common.cancel"), on_click=dialog.close).props("flat")
            ui.button(t("common.create"), on_click=confirm)
    dialog.open()


def open_new_floor_dialog(campus, state, save, floor_select, room_list, render_plan_area):
    if state["building"] is None:
        ui.notify(t("floor.error.select_building_first"), color="warning")
        return

    building = state["building"]
    default_level = (max((f.level for f in building.floors), default=-1)) + 1
    clone_options = {"__none__": t("floor.dialog.clone_none")}
    clone_options.update({f.id: f.name for f in building.floors})

    with ui.dialog() as dialog, ui.card():
        ui.label(t("floor.dialog.title")).classes("text-lg font-semibold")
        name_input = ui.input(t("floor.dialog.name")).classes("w-full")
        level_input = ui.number(
            t("floor.dialog.level"),
            value=default_level,
            precision=0,
        ).classes("w-full")
        clone_select = ui.select(clone_options, value="__none__", label=t("floor.dialog.clone_from")).classes("w-full")

        def confirm() -> None:
            if not name_input.value:
                ui.notify(t("common.name_required"), color="warning")
                return
            level = int(level_input.value if level_input.value is not None else default_level)

            if clone_select.value and clone_select.value != "__none__":
                source_floor = next((f for f in building.floors if f.id == clone_select.value), None)
                if source_floor is None or not source_floor.polygon:
                    ui.notify(t("floor.error.clone_failed"), color="warning")
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
            ui.button(t("common.cancel"), on_click=dialog.close).props("flat")
            ui.button(t("common.create"), on_click=confirm)
    dialog.open()


def open_new_room_dialog(state, save, room_list, render_plan_area):
    if state["floor"] is None:
        ui.notify(t("room.error.select_floor_first"), color="warning")
        return

    with ui.dialog() as dialog, ui.card():
        ui.label(t("room.dialog.title")).classes("text-lg font-semibold")
        name_input = ui.input(t("room.dialog.name")).classes("w-full")
        capacity_input = ui.number(t("room.dialog.capacity"), value=10, min=1, precision=0).classes("w-full")

        def confirm() -> None:
            if not name_input.value:
                ui.notify(t("common.name_required"), color="warning")
                return
            state["mode"] = "placing_room"
            state["pending_room_name"] = name_input.value
            state["pending_room_capacity"] = int(capacity_input.value or 1)
            dialog.close()
            render_plan_area()

        with ui.row().classes("justify-end w-full mt-2"):
            ui.button(t("common.cancel"), on_click=dialog.close).props("flat")
            ui.button(t("room.dialog.place_action"), on_click=confirm)
    dialog.open()
