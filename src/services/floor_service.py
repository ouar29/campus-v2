from __future__ import annotations

from i18n import t
from model import Building, Floor, Point


class FloorService:
    def __init__(self, campus):
        self.campus = campus

    def create_floor(self, building: Building, name: str, polygon, level=None) -> Floor:
        if not name or not name.strip():
            raise ValueError(t("error.floor.name_required"))
        if len(polygon) < 3:
            raise ValueError(t("error.floor.polygon_too_short"))
        return building.add_floor(name.strip(), polygon, level=level)

    def add_vertex(self, floor: Floor, point):
        floor.polygon.append([round(point[0], 2), round(point[1], 2)])

    def remove_vertex(self, floor: Floor, index):
        if len(floor.polygon) > 3:
            floor.polygon.pop(index)

    def insert_vertex(self, floor: Floor, index: int, point):
        floor.polygon.insert(index, [round(point[0], 2), round(point[1], 2)])


MAX_UNDO_STEPS = 50


class FloorGeometryEditor:
    """Pile d'annulation pour l'édition d'un contour d'étage.

    L'édition d'un contour se fait à la souris et chaque geste (déplacer,
    ajouter ou supprimer un sommet) sauvegarde immédiatement `data.json` :
    sans pile d'annulation, un sommet supprimé ou déplacé par erreur ne se
    récupère pas.

    La pile vit en mémoire et est attachée à une *session* d'édition — un
    étage, de « Éditer le contour » à « Terminer l'édition ». Elle ne
    survit donc ni au changement d'étage ni au redémarrage : c'est un
    filet de sécurité sur le geste en cours, pas un historique global du
    campus (celui-ci reste une idée ouverte de la roadmap).
    """

    def __init__(self, max_steps: int = MAX_UNDO_STEPS):
        self.max_steps = max_steps
        self.floor_id: str | None = None
        self.initial: list[Point] | None = None
        self.stack: list[list[Point]] = []

    @staticmethod
    def _snapshot(floor: Floor) -> list[Point]:
        return [list(p) for p in floor.polygon]

    def begin(self, floor: Floor) -> None:
        """Ouvre une session d'édition sur `floor`, en oubliant la précédente."""
        self.floor_id = floor.id
        self.initial = self._snapshot(floor)
        self.stack = []

    def ensure_session(self, floor: Floor) -> None:
        """Ouvre une session si aucune n'est ouverte sur cet étage."""
        if self.floor_id != floor.id:
            self.begin(floor)

    def end(self) -> None:
        self.floor_id = None
        self.initial = None
        self.stack = []

    def push(self, floor: Floor) -> None:
        """Mémorise le contour *avant* la modification qui va suivre."""
        self.ensure_session(floor)
        self.stack.append(self._snapshot(floor))
        if len(self.stack) > self.max_steps:
            self.stack.pop(0)

    def discard_if_unchanged(self, floor: Floor) -> bool:
        """Retire le dernier point de reprise si rien n'a finalement bougé.

        Un simple clic sur un sommet passe par le même `mousedown` qu'un
        glisser : sans ce ménage, cliquer sans déplacer empilerait des
        étapes d'annulation sans effet.
        """
        if self.floor_id != floor.id or not self.stack:
            return False
        if self.stack[-1] == floor.polygon:
            self.stack.pop()
            return True
        return False

    def can_undo(self, floor: Floor) -> bool:
        return self.floor_id == floor.id and bool(self.stack)

    def undo(self, floor: Floor) -> bool:
        if not self.can_undo(floor):
            return False
        floor.polygon = self.stack.pop()
        return True

    def can_reset(self, floor: Floor) -> bool:
        return self.floor_id == floor.id and self.initial is not None and floor.polygon != self.initial

    def reset(self, floor: Floor) -> bool:
        """Revient au contour tel qu'il était à l'ouverture de la session.

        Le retour en arrière est lui-même empilé : annuler juste après un
        « rétablir » restaure le contour que l'on venait d'abandonner.
        """
        if not self.can_reset(floor):
            return False
        self.push(floor)
        floor.polygon = [list(p) for p in self.initial]
        return True
