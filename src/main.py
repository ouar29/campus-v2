"""Point d’entrée minimal du projet campus.

La logique de l’application est maintenant dans src/campus_app.py.
"""
from __future__ import annotations

from campus_app import main

import sys
import os

# 1. Ajuster le chemin si l'application tourne depuis un binaire PyInstaller
if getattr(sys, "frozen", False):
    # Désactive le rechargement automatique interne de NiceGUI
    os.environ["NICEGUI_RELOAD"] = "false"


if __name__ in {"__main__", "__mp_main__"}:
    main()
