"""Dialogue d'accueil : proposé quand le campus courant est vide.

`src/data.json` n'est pas versionné et l'exécutable packagé n'embarque aucune
donnée : un clone frais comme un premier lancement démarrent donc sur un
campus vide, devant un plan sans rien à afficher. Ce dialogue donne les deux
seules suites utiles à ce moment-là — importer un `.cps` existant, ou partir
d'une page blanche — plutôt que de laisser l'utilisateur chercher le bouton
d'import dans l'en-tête.
"""
from __future__ import annotations

from nicegui import ui


def open_welcome_dialog(app) -> None:
    with ui.dialog() as dialog, ui.card().classes("w-[460px] max-w-[92vw]"):
        ui.label("Bienvenue").classes("text-lg font-semibold")
        ui.label(
            "Ce campus est vide. Importe un fichier .cps existant, ou commence "
            "un campus de zéro en créant un premier bâtiment."
        ).classes("text-sm text-gray-600 dark:text-gray-300")

        def start_import() -> None:
            dialog.close()
            app.import_cps_dialog()

        def start_empty() -> None:
            dialog.close()
            app.open_new_building_dialog()

        with ui.column().classes("w-full gap-2 mt-3"):
            ui.button("Importer un .cps", icon="upload_file", on_click=start_import).classes("w-full")
            ui.button("Créer un premier bâtiment", icon="add", on_click=start_empty).props("outline").classes("w-full")
            ui.button("Plus tard", on_click=dialog.close).props("flat").classes("w-full")
    dialog.open()
