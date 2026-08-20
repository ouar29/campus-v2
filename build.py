#!/usr/bin/env python3
"""Empaquette l'application en exécutable autonome (PyInstaller via nicegui-pack).

Usage :
    poetry run python build.py                        # --onedir (démarrage rapide), par défaut
    poetry run python build.py --onefile               # exécutable unique (démarrage plus lent)
    poetry run python build.py --icon assets/icon.ico  # icône personnalisée (.ico Windows / .icns macOS)
    poetry run python build.py --clean --noconfirm      # rebuild propre, sans confirmation

Ce script appelle `nicegui.scripts.pack` (le "nicegui-pack" officiel de NiceGUI)
via `python -m` plutôt que la commande `nicegui-pack` directement : cela évite
les soucis de PATH parfois observés sous Windows avec les scripts installés
par Poetry (le binaire généré n'est pas toujours trouvé par le shell), tout
en produisant exactement le même résultat, puisque c'est le même code.

Le seul ajout par rapport à un `nicegui-pack` nu : le fichier de données par
défaut (src/data.json) est embarqué dans le bundle, à l'emplacement attendu
par `get_resource_path()` (campus_app.py) — c'est le modèle qui sera copié
vers le dossier de données utilisateur au tout premier lancement (voir
`get_data_path()`). Ce fichier embarqué n'est ensuite jamais modifié
directement : en mode --onefile, le dossier du bundle est temporaire et
entièrement effacé à la fermeture de l'application, donc y écrire perdrait
les modifications de l'utilisateur à chaque redémarrage.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
MAIN_SCRIPT = SRC / "main.py"
DEFAULT_DATA = SRC / "data.json"
APP_NAME = "Campus-Admin"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--onefile", action="store_true",
        help="Exécutable unique. Pratique à distribuer, mais démarrage plus lent.",
    )
    mode.add_argument(
        "--onedir", action="store_true",
        help="Dossier avec toutes les dépendances (démarrage rapide). Par défaut.",
    )
    parser.add_argument(
        "--no-windowed", action="store_true",
        help="Garder une console visible (utile pour déboguer un problème de démarrage).",
    )
    parser.add_argument("--icon", type=str, default=None, help="Chemin vers une icône .ico / .icns.")
    parser.add_argument("--clean", action="store_true", help="Nettoie le cache PyInstaller avant de builder.")
    parser.add_argument("--noconfirm", action="store_true", help="Écrase ./dist sans demander confirmation.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not MAIN_SCRIPT.exists():
        sys.exit(f"Script principal introuvable : {MAIN_SCRIPT}")
    if not DEFAULT_DATA.exists():
        sys.exit(f"Données par défaut introuvables : {DEFAULT_DATA}")

    command = [
        sys.executable, "-m", "nicegui.scripts.pack",
        "--name", APP_NAME,
        # Embarque le data.json "modèle" dans le bundle, au même chemin
        # relatif ("src/data.json") que get_resource_path() attend.
        "--add-data", f"{DEFAULT_DATA}{os.pathsep}src",
    ]
    if not args.no_windowed:
        command.append("--windowed")
    command.append("--onefile" if args.onefile else "--onedir")
    if args.icon:
        command.extend(["--icon", args.icon])
    if args.clean:
        command.append("--clean")
    if args.noconfirm:
        command.append("--noconfirm")
    command.append(str(MAIN_SCRIPT))

    print("Commande PyInstaller (via nicegui-pack) :")
    print(" ", " ".join(command))
    subprocess.run(command, check=True, cwd=ROOT)


if __name__ == "__main__":
    main()
