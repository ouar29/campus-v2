"""Validation des fichiers .cps contre un schema JSON.

Le schema est charge depuis campus_schema.json (a placer a cote de ce module,
ou adapter get_schema_path() pour reutiliser le meme mecanisme que
get_resource_path() dans campus_app.py afin de fonctionner aussi bundle
PyInstaller).
"""

from __future__ import annotations

import json

from i18n import t
from pathlib import Path

from jsonschema import Draft202012Validator

# Remplacer par get_resource_path("src/campus_schema.json") si le fichier
# doit etre embarque dans le build PyInstaller (meme mecanisme que pour
# src/data.json dans campus_app.get_data_path()).
SCHEMA_PATH = Path(__file__).parent / "campus_schema.json"


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _format_errors(errors) -> list[str]:
    messages = []
    for error in sorted(errors, key=lambda e: list(e.path)):
        location = " -> ".join(str(part) for part in error.path) or "(racine)"
        messages.append(f"{location} : {error.message}")
    return messages


def validate_campus_bytes(data: bytes) -> list[str]:
    """Valide le contenu brut d'un fichier .cps contre le schema.

    Retourne une liste de messages d'erreur lisibles. Liste vide = valide.
    """
    try:
        payload = json.loads(data.decode("utf-8"))
    except UnicodeDecodeError as exc:
        return [t("validation.error.encoding", error=exc)]
    except json.JSONDecodeError as exc:
        return [t("validation.error.json", message=exc.msg, line=exc.lineno, column=exc.colno)]

    validator = Draft202012Validator(load_schema())
    return _format_errors(validator.iter_errors(payload))


def validate_campus_file(path: Path) -> list[str]:
    """Valide un fichier .cps sur disque contre le schema."""
    try:
        data = path.read_bytes()
    except OSError as exc:
        return [t("validation.error.unreadable_file", error=exc)]
    return validate_campus_bytes(data)
