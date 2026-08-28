"""Lecture des fichiers déposés via `ui.upload` de NiceGUI.

Module volontairement neutre : il ne dépend ni de `campus_app`, ni des vues.
C'est ce qui permet à `campus_app.py` et à `ui/views.py` de partager ce
helper sans créer de cycle d'imports entre eux (`ui/views` importait
auparavant `campus_app`, qui importe `ui/views`).
"""
from __future__ import annotations


async def read_uploaded_file(event) -> tuple[str, bytes] | None:
    """Extrait (nom, contenu) d'un événement d'upload NiceGUI.

    Tolère les variantes de l'API : `event.file` absent, `read()` synchrone
    ou renvoyant un awaitable selon la version de NiceGUI. Renvoie None si
    l'événement ne porte pas de fichier exploitable.
    """
    file = getattr(event, "file", None)
    if file is None:
        return None
    file_name = getattr(file, "name", "") or "campus.cps"
    try:
        data = file.read()
    except TypeError:
        return None
    if hasattr(data, "__await__"):
        data = await data
    return file_name, bytes(data)
