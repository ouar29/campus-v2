from __future__ import annotations

from nicegui import ui


def build_header(campus_app):
    with ui.header().classes("items-center justify-between"):
        ui.label("Administration du Campus").classes("text-lg font-semibold")
        with ui.row().classes("items-center gap-2"):
            ui.button("Importer .cps", icon="upload_file", on_click=campus_app.import_cps_dialog).props("outline color=white")
            ui.button("Exporter .cps", icon="download", on_click=campus_app.export_cps_dialog).props("outline color=white")
            ui.button("Toutes les salles", icon="table_rows", on_click=campus_app.open_room_table_dialog).props("outline color=white")
            ui.button("Plan du campus", icon="map", on_click=campus_app.open_campus_map_dialog).props("outline color=white")
            ui.button("Vue d'ensemble (isométrique)", icon="view_in_ar", on_click=campus_app.open_overview_dialog).props("outline color=white")
            ui.button(icon="light_mode", on_click=campus_app.dark.disable).props("flat round color=white").tooltip("Thème clair").bind_visibility_from(campus_app.dark, "value", value=True)
            ui.button(icon="dark_mode", on_click=campus_app.dark.enable).props("flat round color=white").tooltip("Thème sombre").bind_visibility_from(campus_app.dark, "value", value=False)


def build_sidebar(campus_app):
    with ui.left_drawer().classes("gap-2 p-4"):
        ui.label("Sélection").classes("text-sm font-semibold text-gray-500 dark:text-gray-300")
        campus_app.session_select = ui.select(
            campus_app.session_options(),
            value=campus_app.current_session_key,
            label="Session",
            on_change=lambda e: campus_app.switch_session(e.value),
        ).classes("w-full")

        campus_app.building_select = ui.select(
            campus_app.buildings_options(),
            value=campus_app.state["building"].id if campus_app.state["building"] else None,
            label="Bâtiment",
            on_change=lambda e: campus_app.on_building_change(e.value),
        ).classes("w-full")
        ui.button("+ Bâtiment", on_click=lambda: campus_app.open_new_building_dialog()).props("size=sm outline").classes("w-full")

        campus_app.floor_select = ui.select(
            campus_app.floors_options(campus_app.state["building"]),
            value=campus_app.state["floor"].id if campus_app.state["floor"] else None,
            label="Étage",
            on_change=lambda e: campus_app.on_floor_change(e.value),
        ).classes("w-full")
        ui.button("+ Étage", on_click=lambda: campus_app.open_new_floor_dialog()).props("size=sm outline").classes("w-full")

        ui.separator()
        with ui.row().classes("items-center justify-between w-full"):
            ui.label("Salles de l'étage").classes("text-sm font-semibold text-gray-500 dark:text-gray-300")
            ui.button("+ Salle", on_click=lambda: campus_app.open_new_room_dialog()).props("size=sm outline")
        campus_app.room_list()


def build_main_area(campus_app):
    with ui.column().classes("w-full h-full items-stretch p-4"):
        campus_app.render_plan_area()
