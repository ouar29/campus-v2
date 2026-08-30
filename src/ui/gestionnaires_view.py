"""Dialogue « Gestionnaires » : annuaire partagé au niveau du campus.

Les gestionnaires vivent sur le `Campus`, pas sur les salles : une salle n'en
référence que les identifiants. Supprimer un gestionnaire le retire donc de
toutes les salles qui le citent, d'où la confirmation qui annonce le nombre
de salles impactées.
"""
from __future__ import annotations

from nicegui import ui

from i18n import t
from model import Gestionnaire


def open_gestionnaires_dialog(app) -> None:
    search = {"query": ""}

    def open_edit_dialog(gestionnaire_id: str | None) -> None:
        gestionnaire = app.controller.get_gestionnaire(gestionnaire_id) if gestionnaire_id else None

        with ui.dialog() as edit_dialog, ui.card().classes("w-96"):
            ui.label(t("gestionnaire.edit.title_existing") if gestionnaire else t("gestionnaire.edit.title_new")).classes(
                "text-lg font-semibold mb-2"
            )
            nom_input = ui.input(t("gestionnaire.field.nom"), value=gestionnaire.nom if gestionnaire else "").classes("w-full")
            email_input = ui.input(t("gestionnaire.field.email"), value=gestionnaire.email if gestionnaire else "").classes("w-full")
            tel_input = ui.input(t("gestionnaire.field.telephone"), value=gestionnaire.telephone if gestionnaire else "").classes("w-full")

            def save() -> None:
                nom = (nom_input.value or "").strip()
                if not nom:
                    ui.notify(t("gestionnaire.error.name_required"), color="warning")
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
                ui.button(t("common.cancel"), on_click=edit_dialog.close).props("flat")
                ui.button(t("gestionnaire.action.save"), on_click=save)

        edit_dialog.open()

    def confirm_delete(gestionnaire: Gestionnaire) -> None:
        rooms_using = app.controller.get_rooms_for_gestionnaire(gestionnaire.id)
        with ui.dialog() as confirm_dlg, ui.card():
            message = t("gestionnaire.delete.confirm", nom=gestionnaire.nom)
            if rooms_using:
                message += t("gestionnaire.delete.rooms_impacted", count=len(rooms_using))
            ui.label(message)

            def do_delete() -> None:
                app.controller.delete_gestionnaire(gestionnaire.id)
                confirm_dlg.close()
                rows_view.refresh()

            with ui.row().classes("w-full justify-end mt-2"):
                ui.button(t("common.cancel"), on_click=confirm_dlg.close).props("flat")
                ui.button(t("gestionnaire.action.delete"), color="negative", on_click=do_delete)
        confirm_dlg.open()

    def render_gestionnaire_row(gestionnaire: Gestionnaire) -> None:
        nb_salles = len(app.controller.get_rooms_for_gestionnaire(gestionnaire.id))
        with ui.row().classes("w-full items-center gap-3 py-1 border-b border-gray-100 dark:border-gray-700"):
            ui.label(gestionnaire.nom).classes("w-48 font-medium")
            ui.label(gestionnaire.email or t("gestionnaire.empty_value")).classes("flex-1 text-sm text-gray-600 dark:text-gray-300")
            ui.label(gestionnaire.telephone or t("gestionnaire.empty_value")).classes("w-40 text-sm text-gray-600 dark:text-gray-300")
            ui.label(t("gestionnaire.rooms_count", count=nb_salles)).classes("w-28 text-sm text-gray-500 dark:text-gray-300")
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
            ui.label(t("gestionnaire.search.no_match")).classes(
                "text-gray-500 dark:text-gray-300 py-4"
            )

    def on_search_change(e) -> None:
        search["query"] = e.value or ""
        rows_view.refresh()

    with ui.dialog().props("maximized") as dialog, ui.card().classes("w-full h-full"):
        with ui.row().classes("items-center justify-between w-full mb-2"):
            ui.label(t("gestionnaire.dialog.title")).classes("text-lg font-semibold")
            with ui.row().classes("items-center gap-2"):
                ui.button(t("gestionnaire.dialog.add"), icon="add", on_click=lambda: open_edit_dialog(None)).props(
                    "size=sm color=primary"
                )
                ui.button(icon="close", on_click=dialog.close).props("flat round")

        ui.input(
            label=t("gestionnaire.dialog.search"),
            on_change=on_search_change,
        ).classes("w-full mb-2").props("clearable dense outlined")

        with ui.scroll_area().classes("w-full h-full"):
            with ui.row().classes(
                "w-full items-center gap-3 pb-2 border-b-2 border-gray-300 dark:border-gray-600 "
                "text-sm font-semibold text-gray-500 dark:text-gray-300"
            ):
                ui.label(t("gestionnaire.field.nom")).classes("w-48")
                ui.label(t("gestionnaire.field.email")).classes("flex-1")
                ui.label(t("gestionnaire.field.telephone")).classes("w-40")
                ui.label(t("gestionnaire.column.rooms")).classes("w-28")

            rows_view()

    dialog.open()
