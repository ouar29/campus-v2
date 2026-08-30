from __future__ import annotations

from geometry import polygon_centroid
from model import PENDING_BUILDING_NAME, Building, Floor, Room

# --- Prédicats d'intérêt sur une salle -----------------------------------
# Ils décrivent des situations métier ("cette salle a un problème", "cette
# salle attend un traitement"), pas une mise en forme : la table des salles
# les assemble en filtres prédéfinis, mais ils restent utilisables ailleurs
# (rapport d'intégrité, export). Fonctions libres plutôt que méthodes : elles
# ne dépendent que de l'entité passée, pas du campus.


def is_unavailable(room: Room) -> bool:
    """Salle marquée indisponible dans le `.cps` d'origine (`extra.available`)."""
    return not room.extra.get("available", True)


def has_no_gestionnaire(room: Room) -> bool:
    return not room.gestionnaire_ids


def has_suspicious_capacity(room: Room) -> bool:
    """Capacité absente ou nulle : typiquement une salle importée à trous."""
    return not room.capacity or room.capacity <= 0


def is_awaiting_placement(building: Building) -> bool:
    """Salle encore dans le bâtiment placeholder de campus-factory."""
    return building.name == PENDING_BUILDING_NAME


class RoomService:
    def __init__(self, campus):
        self.campus = campus

    def create_room(self, floor: Floor, name: str, capacity: int, position) -> Room:
        if not name or not name.strip():
            raise ValueError("Le nom de la salle est requis")
        capacity = int(capacity)
        if capacity < 1:
            raise ValueError("La capacité doit être au moins 1")
        return floor.add_room(name.strip(), capacity, [round(position[0], 2), round(position[1], 2)])

    def move_room(self, source_floor: Floor, room: Room, target_floor: Floor) -> bool:
        if target_floor is source_floor:
            return False
        source_floor.rooms = [r for r in source_floor.rooms if r.id != room.id]
        room.position = polygon_centroid(target_floor.polygon)
        target_floor.rooms.append(room)
        return True
