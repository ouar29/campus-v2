"""Convertit un export .cps (schéma d'un autre projet) vers notre data.json.

Mapping constaté sur le fichier fourni :
  campus.cps                          -> notre modèle (model.py)
  ---------------------------------------------------------------
  {name, buildings, version, ...}     -> Campus(name, buildings, extra={...})
  building.location.{x,y}             -> Building.position
  building.name / building.id         -> Building.name / id
  floor.name                          -> Floor.name (conservé tel quel)
  floor.name (si entier, ex: "0","-1")-> Floor.level  (repli : index dans la liste)
  floor.points (liste plate x,y,x,y…) -> Floor.polygon (liste de [x, y])
  room.location.{x,y}                 -> Room.position
  room.name / room.capacity / room.id -> Room.name / capacity / id

IMPORTANT — fidélité de ré-export : chaque entité conserve dans son champ
`extra` une copie de TOUS ses champs d'origine (id numérique, location
complète avec z/hash, dimensions, zoneMarkers, access, equipments,
roomManagers, comment, zone, roomType, etc.), à l'exception du seul champ
« enfants » qu'on reconstruit nous-mêmes récursivement (floors/rooms).
Cela permet à export_cps.py de reconstruire un fichier quasi identique à
l'original, en n'y répercutant que ce que l'utilisateur a réellement
modifié dans notre appli (nom, capacité, position, contour).

Seules les salles avec roomType == "meetingRoom" sont importées dans le
modèle éditable (le fichier source peut contenir d'autres types de pièces
hors du périmètre de cette application). Les salles ignorées ne seront
donc pas reprises non plus lors d'un ré-export ultérieur — voir la note
correspondante affichée par ce script.

Usage :
    python import_cps.py chemin/vers/fichier.cps [chemin/vers/data.json]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from model import Campus, Building, Floor, Room


def _load_json_lenient(path: str) -> dict:
    """Charge le JSON en tolérant les virgules traînantes avant } ou ] :
    certains exports du projet source semblent en produire (bug côté export,
    pas du JSON strictement valide). On tente d'abord un parsing strict ;
    en cas d'échec, on retire les virgules traînantes et on réessaie."""
    text = Path(path).read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as first_error:
        cleaned = re.sub(r",(\s*[}\]])", r"\1", text)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            raise first_error  # le nettoyage n'a pas suffi : on remonte l'erreur d'origine
        print(
            f"Attention : {path} contenait des virgules traînantes non valides en JSON strict "
            "(corrigées automatiquement à la lecture). Vérifie l'outil d'export source si ça se répète."
        )
        return data


def _parse_level(name: str, fallback_index: int) -> int:
    try:
        return int(str(name).strip())
    except (TypeError, ValueError):
        return fallback_index


def _points_to_polygon(points: list[float]) -> list[list[float]]:
    return [[points[i], points[i + 1]] for i in range(0, len(points) - 1, 2)]


def convert(cps_path: str) -> tuple[Campus, int]:
    """Retourne (Campus converti, nombre de salles ignorées car hors périmètre)."""
    raw = _load_json_lenient(cps_path)

    campus_extra = {k: v for k, v in raw.items() if k != "buildings"}
    campus = Campus(id="campus-imported", name=raw.get("name", "Campus importé"), extra=campus_extra)
    skipped_rooms = 0

    for b in raw.get("buildings", []):
        building_extra = {k: v for k, v in b.items() if k != "floors"}
        building = Building(
            id=f"bldg-{b['id']}",
            name=b.get("name", f"Bâtiment {b['id']}"),
            position=[b.get("location", {}).get("x", 0.0), b.get("location", {}).get("y", 0.0)],
            extra=building_extra,
        )

        for f_index, f in enumerate(b.get("floors", [])):
            floor_extra = {k: v for k, v in f.items() if k != "rooms"}
            floor = Floor(
                id=f"floor-{f['id']}",
                name=f.get("name", str(f_index)),
                level=_parse_level(f.get("name", f_index), f_index),
                polygon=_points_to_polygon(f.get("points", [])),
                extra=floor_extra,
            )

            for r in f.get("rooms", []):
                if r.get("roomType") != "meetingRoom":
                    skipped_rooms += 1
                    continue
                floor.rooms.append(
                    Room(
                        id=f"room-{r['id']}",
                        name=r.get("name", f"Salle {r['id']}"),
                        capacity=int(r.get("capacity") or 1),
                        position=[r.get("location", {}).get("x", 0.0), r.get("location", {}).get("y", 0.0)],
                        extra=dict(r),
                    )
                )

            building.floors.append(floor)

        campus.buildings.append(building)

    return campus, skipped_rooms


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage : python import_cps.py chemin/vers/fichier.cps [chemin/vers/data.json]")
        sys.exit(1)

    cps_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else "data.json"

    campus, skipped = convert(cps_path)
    campus.save(out_path)

    nb_buildings = len(campus.buildings)
    nb_floors = sum(len(b.floors) for b in campus.buildings)
    nb_rooms = sum(len(f.rooms) for b in campus.buildings for f in b.floors)
    print(f"Importé : {nb_buildings} bâtiment(s), {nb_floors} étage(s), {nb_rooms} salle(s) -> {out_path}")
    if skipped:
        print(f"Ignoré : {skipped} pièce(s) dont le roomType n'est pas 'meetingRoom' (non ré-exportables)")
