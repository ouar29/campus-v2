"""Catalogue des libellés de l'application.

Toutes les chaînes affichées à l'utilisateur vivent dans un catalogue par
langue (`fr.py`) et sont récupérées par `t("clé")`. Le français est la seule
langue pour l'instant ; le point de cette indirection est d'avoir un endroit
unique où relire, corriger et — le jour venu — traduire le vocabulaire de
l'appli, plutôt que 229 chaînes disséminées dans 24 fichiers.

Ce module suit la même règle que `theme.py` : **aucune dépendance à
NiceGUI**, pour rester importable par les services et la couche de rendu SVG
autant que par les vues.

Ce qui n'entre PAS dans le catalogue :

- les identifiants techniques (noms d'icônes, classes CSS, props Quasar) ;
- les messages des scripts en ligne de commande (`import_cps.py`,
  `export_cps.py` lancés à la main), qui s'adressent au développeur ;
- `model.PENDING_BUILDING_NAME`, qui n'est pas un libellé mais une **valeur
  de données** devant rester identique à celle de campus-factory : la
  traduire casserait le rapprochement des salles à positionner.
"""
from __future__ import annotations

import sys

from i18n.fr import MESSAGES

DEFAULT_LOCALE = "fr"
CATALOGUES = {"fr": MESSAGES}


def t(key: str, **params: object) -> str:
    """Libellé associé à `key`, avec interpolation nommée optionnelle.

    Une clé inconnue **ne lève pas** : elle est signalée sur la sortie
    d'erreur et rendue telle quelle. La page NiceGUI est construite à chaque
    requête (voir `campus_app.main()`), donc une exception ici se traduirait
    par un HTTP 500 muet dans le navigateur — perdre un libellé est
    préférable à perdre la page. Le vrai filet est statique : le test
    `tests/test_i18n.py` vérifie que toute clé écrite en dur dans le code
    existe bien dans le catalogue.
    """
    template = CATALOGUES[DEFAULT_LOCALE].get(key)
    if template is None:
        print(f"i18n : clé inconnue « {key} »", file=sys.stderr)
        return key
    if not params:
        return template
    try:
        return template.format(**params)
    except (KeyError, IndexError) as exc:
        print(f"i18n : paramètre manquant pour « {key} » ({exc})", file=sys.stderr)
        return template
