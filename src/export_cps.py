"""Ré-exporte notre data.json vers le format .cps d'origine (autre projet).

Pour chaque entité, on repart de son `extra` (champs d'origine préservés à
l'import — voir import_cps.py) et on n'y écrase que ce que l'utilisateur a
pu modifier dans notre appli : nom, capacité, position (x, y), niveau/nom
d'étage, contour. Tout le reste (access, equipments, roomManagers,
dimensions, zoneMarkers, id numérique d'origine, etc.) est repris tel quel.

Pour une entité créée entièrement dans notre appli (pas d'`extra` d'origine,
ex : nouveau bâtiment/étage/salle), des valeurs par défaut raisonnables sont
appliquées pour que le fichier exporté reste valide vis-à-vis du schéma
d'origine — à vérifier/ajuster côté autre projet si des champs spécifiques
sont requis au-delà de ceux connus ici.

Usage :
    python export_cps.py [chemin/vers/data.json] [chemin/vers/sortie.cps]
"""
from __future__ import annotations

import itertools
import json
import sys
from datetime import date
from pathlib import Path

from model import Campus, Building, Floor, Gestionnaire, Room

_id_counter = itertools.count(900_000)  # ids synthétiques pour les entités créées dans l'appli


def _default_location() -> dict:
    return {"x": 0.0, "y": 0.0, "z": 0.0, "hash": 0}


def _default_dimensions() -> dict:
    return {"width": 1.0, "height": 1.0, "hash": 0}


def _next_synthetic_id() -> int:
    return next(_id_counter)


def export_room(room: Room, gestionnaire_by_id: dict[str, Gestionnaire]) -> dict:
    out = dict(room.extra)
    out["id"] = room.extra.get("id", _next_synthetic_id())
    out["name"] = room.name
    out["capacity"] = room.capacity
    base_location = dict(room.extra.get("location", _default_location()))
    base_location["x"], base_location["y"] = room.position[0], room.position[1]
    out["location"] = base_location
    out.setdefault("roomType", "meetingRoom")
    out.setdefault("dimensions", _default_dimensions())
    out.setdefault("oldName", "")
    out.setdefault("altName", "")
    # roomManagers n'est plus une liste libre par salle : c'est désormais
    # reconstruit à partir de l'annuaire partagé (campus.gestionnaires) via
    # room.gestionnaire_ids, seule source de vérité côté modèle. On écrase
    # volontairement toute valeur restée dans `extra` plutôt que de s'y fier.
    out["roomManagers"] = {
        "value": [
            {
                "name": gestionnaire.nom,
                "telephoneNumber": gestionnaire.telephone,
                "email": gestionnaire.email,
            }
            for gid in room.gestionnaire_ids
            if (gestionnaire := gestionnaire_by_id.get(gid)) is not None
        ]
    }
    out.setdefault("access", "NONE")
    out.setdefault("available", True)
    out.setdefault("equipments", [])
    out.setdefault("roomBookingType", "")
    out.setdefault("comment", "")
    out.setdefault("zone", "")
    out.setdefault("telephoneNumber", "")
    out.setdefault("type", "NONE")
    return out


def export_floor(floor: Floor, gestionnaire_by_id: dict[str, Gestionnaire]) -> dict:
    out = {k: v for k, v in floor.extra.items() if k != "rooms"}
    out["id"] = floor.extra.get("id", _next_synthetic_id())
    out["name"] = floor.name
    flat_points: list[float] = []
    for x, y in floor.polygon:
        flat_points.extend([x, y])
    out["points"] = flat_points
    out["rooms"] = [export_room(r, gestionnaire_by_id) for r in floor.rooms]
    out.setdefault("zoneMarkers", [])
    out.setdefault("dimensions", _default_dimensions())
    out.setdefault("location", _default_location())
    return out


def export_building(building: Building, gestionnaire_by_id: dict[str, Gestionnaire]) -> dict:
    out = {k: v for k, v in building.extra.items() if k != "floors"}
    out["id"] = building.extra.get("id", _next_synthetic_id())
    out["name"] = building.name
    base_location = dict(building.extra.get("location", _default_location()))
    base_location["x"], base_location["y"] = building.position[0], building.position[1]
    out["location"] = base_location
    out["floors"] = [export_floor(f, gestionnaire_by_id) for f in building.floors]
    return out


def export_campus(campus: Campus) -> dict:
    gestionnaire_by_id = {g.id: g for g in campus.gestionnaires}
    out = {k: v for k, v in campus.extra.items() if k != "buildings"}
    out["name"] = campus.name
    out["version"] = date.today().isoformat()
    out["buildings"] = [export_building(b, gestionnaire_by_id) for b in campus.buildings]
    return out


if __name__ == "__main__":
    in_path = sys.argv[1] if len(sys.argv) > 1 else "data.json"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "campus_export.cps"

    campus = Campus.load(in_path)
    exported = export_campus(campus)
    Path(out_path).write_text(json.dumps(exported, indent=2, ensure_ascii=False), encoding="utf-8")

    nb_buildings = len(campus.buildings)
    nb_floors = sum(len(b.floors) for b in campus.buildings)
    nb_rooms = sum(len(f.rooms) for b in campus.buildings for f in b.floors)
    print(f"Exporté : {nb_buildings} bâtiment(s), {nb_floors} étage(s), {nb_rooms} salle(s) -> {out_path}")
