from model import Gestionnaire
from nicegui import ui


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