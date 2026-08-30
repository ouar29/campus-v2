"""Garde-fou statique du catalogue de libellés.

Les vues NiceGUI ne sont pas couvertes par les tests (elles construisent l'UI
par effet de bord), donc une clé mal orthographiée ne se verrait qu'à
l'exécution, dans la page. Ces tests remplacent ce filet manquant : ils
lisent le code source et confrontent les clés écrites en dur au catalogue.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from i18n import t
from i18n.fr import MESSAGES

SRC = Path(__file__).resolve().parent.parent / "src"
PARAM_PATTERN = re.compile(r"{(\w+)}")


def _source_files() -> list[Path]:
    return sorted(p for p in SRC.rglob("*.py") if "i18n" not in p.parts)


def _t_calls() -> list[tuple[Path, ast.Call]]:
    """Tous les appels `t(...)` du code source, avec leur fichier."""
    calls = []
    for path in _source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "t":
                calls.append((path, node))
    return calls


def _literal_keys() -> dict[str, list[Path]]:
    used: dict[str, list[Path]] = {}
    for path, call in _t_calls():
        if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
            used.setdefault(call.args[0].value, []).append(path)
    return used


def test_every_key_used_in_the_code_exists_in_the_catalogue():
    unknown = {
        key: [p.name for p in paths]
        for key, paths in _literal_keys().items()
        if key not in MESSAGES
    }
    assert not unknown, f"Clés absentes du catalogue : {unknown}"


def test_the_catalogue_has_no_dead_keys():
    """Une clé qui ne sert plus est du vocabulaire fantôme : on la retire."""
    unused = sorted(set(MESSAGES) - set(_literal_keys()))
    assert not unused, f"Clés du catalogue jamais utilisées : {unused}"


def test_every_t_call_uses_a_literal_key():
    """Une clé calculée échapperait aux deux vérifications ci-dessus."""
    dynamic = [
        f"{path.name}:{call.lineno}"
        for path, call in _t_calls()
        if not (call.args and isinstance(call.args[0], ast.Constant))
    ]
    assert not dynamic, f"Appels t() à clé non littérale : {dynamic}"


def test_named_parameters_of_each_message_are_provided_by_its_callers():
    """Les paramètres sont nommés : un `{name}` non fourni sort en clair."""
    provided: dict[str, set[str]] = {}
    for _, call in _t_calls():
        if call.args and isinstance(call.args[0], ast.Constant):
            key = call.args[0].value
            names = {kw.arg for kw in call.keywords if kw.arg}
            provided.setdefault(key, set()).update(names)

    missing = {}
    for key, template in MESSAGES.items():
        expected = set(PARAM_PATTERN.findall(template))
        if key in provided and not expected <= provided[key]:
            missing[key] = sorted(expected - provided[key])
    assert not missing, f"Paramètres non fournis à t() : {missing}"


def test_unknown_key_degrades_instead_of_breaking_the_page(capsys):
    # La page est reconstruite à chaque requête : lever ici donnerait un
    # HTTP 500 muet plutôt qu'un libellé manquant.
    assert t("clé.qui.nexiste.pas") == "clé.qui.nexiste.pas"
    assert "clé inconnue" in capsys.readouterr().err


def test_catalogue_style_is_consistent():
    """Apostrophe droite et tutoiement : décidés une fois, vérifiés ici."""
    typographic = sorted(key for key, value in MESSAGES.items() if "’" in value)
    assert not typographic, f"Apostrophe typographique (’) au lieu de ' : {typographic}"

    vouvoiement = re.compile(r"\b(cliquez|sélectionnez|choisissez|créez|importez|glissez)\b", re.IGNORECASE)
    formal = sorted(key for key, value in MESSAGES.items() if vouvoiement.search(value))
    assert not formal, f"Vouvoiement alors que l'appli tutoie : {formal}"


@pytest.mark.parametrize("key", sorted(MESSAGES))
def test_no_message_is_empty(key):
    assert MESSAGES[key].strip(), f"Libellé vide pour {key}"
