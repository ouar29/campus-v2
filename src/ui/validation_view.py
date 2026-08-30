"""Dialogue « Valider un .cps » : contrôle de conformité au schéma.

Volontairement sans effet de bord sur la session : le fichier déposé est
vérifié contre `campus_schema.json` puis oublié, jamais importé.
"""
from __future__ import annotations

from nicegui import ui

from i18n import t
from schema_validation import validate_campus_bytes
from ui.uploads import read_uploaded_file


def open_validation_dialog(_event=None) -> None:
    with ui.dialog() as dialog, ui.card().classes("w-[28rem]"):
        ui.label(t("validation.dialog.title")).classes("text-lg font-bold")
        ui.label(t("validation.dialog.hint")).classes("text-sm text-gray-500")

        result_container = ui.column().classes("w-full gap-1")

        async def handle_upload(event) -> None:
            result_container.clear()
            read = await read_uploaded_file(event)
            if read is None:
                ui.notify(t("validation.upload.unreadable"), type="negative")
                return

            file_name, data = read
            errors = validate_campus_bytes(data)

            with result_container:
                if not errors:
                    ui.label(t("validation.result.valid", file_name=file_name)).classes(
                        "text-green-600 font-medium"
                    )
                else:
                    ui.label(
                        t("validation.result.errors", count=len(errors), file_name=file_name)
                    ).classes("text-red-600 font-medium")
                    with ui.scroll_area().classes("w-full h-48 border rounded p-2"):
                        for message in errors:
                            ui.label(t("validation.result.error_item", message=message)).classes("text-sm")

        ui.upload(on_upload=handle_upload, auto_upload=True).props(
            "accept=.cps,.json"
        ).classes("w-full")

        with ui.row().classes("w-full justify-end"):
            ui.button(t("common.close"), on_click=dialog.close)

    dialog.open()
