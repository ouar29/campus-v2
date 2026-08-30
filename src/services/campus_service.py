from __future__ import annotations

from geometry import building_local_bounds, rectangle_polygon
from i18n import t
from model import Campus, Building

MAX_MODULAR_FLOORS = 60


def default_floor_name(level: int) -> str:
    """Nom d'étage conventionnel pour un niveau donné (0 = RDC)."""
    if level == 0:
        return t("floor.name.ground")
    if level < 0:
        return t("floor.name.basement", level=level)
    return t("floor.name.first") if level == 1 else t("floor.name.numbered", level=level)


class CampusService:
    def __init__(self, campus: Campus):
        self.campus = campus

    def create_building(self, name: str) -> Building:
        if not name or not name.strip():
            raise ValueError(t("error.building.name_required"))
        return self.campus.add_building(name.strip())

    def rename_campus(self, name: str) -> str:
        """Renomme le campus courant et retourne le nom retenu.

        `Campus.name` n'est pas décoratif : c'est le champ `name` du fichier
        `.cps` produit par `export_cps.py`, et il sert de nom par défaut au
        fichier d'export. Un nom vide casserait les deux.
        """
        if not name or not name.strip():
            raise ValueError(t("error.campus.name_required"))
        self.campus.name = name.strip()
        return self.campus.name

    def create_modular_building(
        self,
        name: str,
        width: float,
        depth: float,
        floor_count: int = 1,
        lowest_level: int = 0,
        position: list[float] | None = None,
    ) -> Building:
        """Crée un bâtiment rectangulaire dont tous les étages ont la même géométrie.

        `width` / `depth` sont exprimés dans les unités du plan (les mêmes que
        les contours d'étage et les positions de bâtiment). Les niveaux vont de
        `lowest_level` à `lowest_level + floor_count - 1`, chacun recevant une
        copie indépendante du même rectangle : les étages restent éditables
        séparément ensuite, comme n'importe quel contour dessiné à la main.
        """
        if not name or not name.strip():
            raise ValueError(t("error.building.name_required"))
        if width <= 0 or depth <= 0:
            raise ValueError(t("error.building.size_positive"))
        floor_count = int(floor_count)
        if floor_count < 1:
            raise ValueError(t("error.building.at_least_one_level"))
        if floor_count > MAX_MODULAR_FLOORS:
            raise ValueError(t("error.building.too_many_levels", maximum=MAX_MODULAR_FLOORS))

        building = self.campus.add_building(name.strip(), position=position)
        polygon = rectangle_polygon(width, depth)
        for level in range(int(lowest_level), int(lowest_level) + floor_count):
            building.add_floor(default_floor_name(level), [list(p) for p in polygon], level=level)
        return building

    def resize_building(self, building: Building, width: float, depth: float) -> None:
        """Met l'empreinte du bâtiment à l'échelle demandée (largeur × profondeur).

        Tous les contours d'étage et toutes les positions de salle sont mis à
        l'échelle du même facteur, depuis le coin bas-gauche de l'empreinte :
        les salles restent à leur place relative dans le bâtiment.
        """
        if width <= 0 or depth <= 0:
            raise ValueError(t("error.building.size_positive"))
        bounds = building_local_bounds(building)
        if bounds is None:
            raise ValueError(t("error.building.no_polygon_to_resize"))
        min_x, min_y, max_x, max_y = bounds
        current_w, current_h = max_x - min_x, max_y - min_y
        if current_w <= 0 or current_h <= 0:
            raise ValueError(t("error.building.degenerate_footprint"))

        scale_x, scale_y = width / current_w, depth / current_h
        for floor in building.floors:
            floor.polygon = [
                [round(min_x + (x - min_x) * scale_x, 2), round(min_y + (y - min_y) * scale_y, 2)]
                for x, y in floor.polygon
            ]
            for room in floor.rooms:
                room.position = [
                    round(min_x + (room.position[0] - min_x) * scale_x, 2),
                    round(min_y + (room.position[1] - min_y) * scale_y, 2),
                ]

    def save(self, path: str):
        self.campus.save(path)
