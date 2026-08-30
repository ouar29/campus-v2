from __future__ import annotations

from nicegui import ui

from i18n import t


def build_header(campus_app):
    with ui.header().classes("items-center justify-between"):
        ui.label(t("app.title")).classes("text-lg font-semibold")
        with ui.row().classes("items-center gap-2"):
            ui.button(t("header.import_cps"), icon="upload_file", on_click=campus_app.import_cps_dialog).props("outline color=white")
            ui.button(t("header.export_cps"), icon="download", on_click=campus_app.export_cps_dialog).props("outline color=white")
            ui.button(t("header.validate_cps"), icon="fact_check", on_click=campus_app.open_validation_dialog).props("outline color=white")
            ui.button(t("header.room_table"), icon="table_rows", on_click=campus_app.open_room_table_dialog).props("outline color=white")
            ui.button(t("header.gestionnaires"), icon="badge", on_click=campus_app.open_gestionnaires_dialog).props("outline color=white")
            ui.button(t("header.campus_map"), icon="map", on_click=campus_app.open_campus_map_dialog).props("outline color=white")
            ui.button(t("header.overview"), icon="view_in_ar", on_click=campus_app.open_overview_dialog).props("outline color=white")
            # Passe par set_dark_mode() et non par dark.enable/disable : le
            # plan SVG est généré côté serveur et doit être redessiné avec la
            # palette du nouveau thème.
            ui.button(icon="light_mode", on_click=lambda: campus_app.set_dark_mode(False)).props("flat round color=white").tooltip(t("header.theme.light")).bind_visibility_from(campus_app.dark, "value", value=True)
            ui.button(icon="dark_mode", on_click=lambda: campus_app.set_dark_mode(True)).props("flat round color=white").tooltip(t("header.theme.dark")).bind_visibility_from(campus_app.dark, "value", value=False)


def build_sidebar(campus_app):
    with ui.left_drawer().classes("gap-3 p-4"):
        # --- Session : quel campus (fichier importé) je consulte ---
        # Card à part entière, bien distincte du reste : changer de session
        # n'a rien à voir avec naviguer dans un bâtiment/étage/salle.
        with ui.card().classes(
            "w-full gap-2 bg-indigo-50 dark:bg-indigo-950/40 "
            "border border-indigo-200 dark:border-indigo-800/60 shadow-sm"
        ):
            with ui.row().classes("items-center gap-2"):
                ui.icon("folder_open").classes("text-indigo-600 dark:text-indigo-300")
                ui.label(t("sidebar.session.title")).classes("text-sm font-semibold text-indigo-700 dark:text-indigo-200")

            campus_app.session_select = ui.select(
                campus_app.session_options(),
                value=campus_app.current_session_key,
                label=t("sidebar.session.select"),
                on_change=lambda e: campus_app.switch_session(e.value),
            ).classes("w-full")

            # Nom du campus : c'est le champ `name` du .cps exporté, pas une
            # simple étiquette d'affichage. Il s'affiche en lecture, et le
            # crayon révèle le champ de saisie — le renommage est un geste
            # délibéré, pas une frappe qui réécrit data.json au fil de l'eau.
            name_state = {"editing": False}

            @ui.refreshable
            def campus_name_view() -> None:
                if not name_state["editing"]:
                    with ui.row().classes("items-center gap-1 w-full no-wrap"):
                        ui.label(campus_app.campus.name or t("sidebar.campus.unnamed")).classes(
                            "text-sm font-medium text-indigo-800 dark:text-indigo-100 truncate grow"
                        ).tooltip(campus_app.campus.name)
                        ui.button(icon="edit", on_click=start_edit).props(
                            "flat dense round size=sm color=indigo"
                        ).tooltip(t("sidebar.campus.rename"))
                    return

                name_input = ui.input(label=t("sidebar.campus.name"), value=campus_app.campus.name).props(
                    "dense outlined autofocus"
                ).classes("w-full")
                # Entrée valide, comme dans n'importe quel champ de renommage.
                name_input.on("keydown.enter", lambda _: confirm(name_input.value))
                with ui.row().classes("justify-end w-full gap-1"):
                    ui.button(t("common.cancel"), on_click=stop_edit).props("flat dense size=sm")
                    ui.button(
                        t("sidebar.campus.rename_action"), on_click=lambda: confirm(name_input.value)
                    ).props("dense size=sm color=primary")

            def start_edit() -> None:
                name_state["editing"] = True
                campus_name_view.refresh()

            def stop_edit() -> None:
                name_state["editing"] = False
                campus_name_view.refresh()

            def confirm(value: str) -> None:
                # Un nom refusé (vide) garde le champ ouvert : l'utilisateur
                # doit pouvoir corriger sans rouvrir l'édition.
                if campus_app.rename_campus(value):
                    stop_edit()

            campus_app.campus_name_view = campus_name_view
            campus_name_view()

            campus_app.version_info()

        # --- Sélection : où je me trouve dans le campus courant ---
        # Bâtiment + étage + salles regroupés ensemble, nettement séparés
        # de la session ci-dessus.
        with ui.card().classes("w-full gap-2 border border-gray-200 dark:border-gray-700 shadow-sm"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("apartment").classes("text-gray-500 dark:text-gray-300")
                ui.label(t("sidebar.selection.title")).classes("text-sm font-semibold text-gray-500 dark:text-gray-300")

            campus_app.building_select = ui.select(
                campus_app.buildings_options(),
                value=campus_app.state["building"].id if campus_app.state["building"] else None,
                label=t("sidebar.building.select"),
                on_change=lambda e: campus_app.on_building_change(e.value),
            ).classes("w-full")
            ui.button(t("sidebar.building.add"), on_click=lambda: campus_app.open_new_building_dialog()).props("size=sm outline").classes("w-full")

            campus_app.floor_select = ui.select(
                campus_app.floors_options(campus_app.state["building"]),
                value=campus_app.state["floor"].id if campus_app.state["floor"] else None,
                label=t("sidebar.floor.select"),
                on_change=lambda e: campus_app.on_floor_change(e.value),
            ).classes("w-full")
            ui.button(t("sidebar.floor.add"), on_click=lambda: campus_app.open_new_floor_dialog()).props("size=sm outline").classes("w-full")

            ui.separator()
            with ui.row().classes("items-center justify-between w-full"):
                ui.label(t("sidebar.rooms.title")).classes("text-sm font-semibold text-gray-500 dark:text-gray-300")
                ui.button(t("sidebar.rooms.add"), on_click=lambda: campus_app.open_new_room_dialog()).props("size=sm outline")
            campus_app.room_list()


def build_main_area(campus_app):
    with ui.column().classes("w-full h-full items-stretch p-4"):
        campus_app.render_plan_area()
