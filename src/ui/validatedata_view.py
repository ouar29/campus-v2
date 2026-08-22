from nicegui import ui
from schema_validation import validate_campus_bytes
from campus_app import _read_uploaded_file

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
