from __future__ import annotations

from model import Building, Floor

PADDING = 2.0
SCALE = 20
DEFAULT_CANVAS_W = 50.0
DEFAULT_CANVAS_H = 30.0
ROOM_RADIUS_UNITS = 1.0
DRAG_THRESHOLD_UNITS = 1.5
CAMPUS_ICON_SIZE = 8.0
CAMPUS_PADDING = 15.0
VERTEX_DRAG_THRESHOLD = 1.2
EDGE_INSERT_THRESHOLD = 0.9


def bounding_box(polygon: list[list[float]]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return min(xs), min(ys), max(xs), max(ys)


def transform_for_floor(floor: Floor | None) -> tuple[float, float, float, float]:
    """Retourne (min_x, min_y, w_units, h_units) pour le repère d'affichage."""
    if floor and floor.polygon:
        min_x, min_y, max_x, max_y = bounding_box(floor.polygon)
        return min_x - PADDING, min_y - PADDING, (max_x - min_x) + 2 * PADDING, (max_y - min_y) + 2 * PADDING
    return -PADDING, -PADDING, DEFAULT_CANVAS_W + 2 * PADDING, DEFAULT_CANVAS_H + 2 * PADDING


def world_to_px(x: float, y: float, origin_x: float, origin_y: float) -> tuple[float, float]:
    return (x - origin_x) * SCALE, (y - origin_y) * SCALE


def px_to_world(px: float, py: float, origin_x: float, origin_y: float) -> tuple[float, float]:
    return px / SCALE + origin_x, py / SCALE + origin_y


def _reference_floor(building: Building) -> Floor | None:
    """Étage de référence pour l'empreinte au sol : le niveau 0 si présent."""
    if not building.floors:
        return None
    zero = next((f for f in building.floors if f.level == 0), None)
    return zero if zero is not None else min(building.floors, key=lambda f: f.level)


def building_footprint(building: Building) -> list[list[float]]:
    """Polygone réel (coordonnées monde) de l'empreinte du bâtiment."""
    floor = _reference_floor(building)
    bx, by = building.position
    if floor is not None and floor.polygon:
        return [[bx + x, by + y] for x, y in floor.polygon]
    half = CAMPUS_ICON_SIZE / 2
    return [[bx - half, by - half], [bx + half, by - half], [bx + half, by + half], [bx - half, by + half]]


def campus_transform(campus) -> tuple[float, float, float, float]:
    """Retourne (origin_x, origin_y, w_units, h_units) pour le plan du campus."""
    if campus.buildings:
        all_pts = [p for b in campus.buildings for p in building_footprint(b)]
        xs = [p[0] for p in all_pts]
        ys = [p[1] for p in all_pts]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
    else:
        min_x, max_x, min_y, max_y = 0.0, 60.0, 0.0, 40.0
    return (
        min_x - CAMPUS_PADDING,
        min_y - CAMPUS_PADDING,
        (max_x - min_x) + 2 * CAMPUS_PADDING,
        (max_y - min_y) + 2 * CAMPUS_PADDING,
    )


def nearest_vertex(polygon: list[list[float]], wx: float, wy: float) -> tuple[int | None, float]:
    if not polygon:
        return None, float("inf")
    best_i, best_dist = None, float("inf")
    for i, (x, y) in enumerate(polygon):
        dist = ((x - wx) ** 2 + (y - wy) ** 2) ** 0.5
        if dist < best_dist:
            best_i, best_dist = i, dist
    return best_i, best_dist


def nearest_edge_insertion(polygon: list[list[float]], wx: float, wy: float, threshold: float) -> tuple[int, list[float]] | None:
    """Trouve le point le plus proche sur une arête du polygone."""
    n = len(polygon)
    best = None
    best_dist = threshold
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        seg_len2 = dx * dx + dy * dy
        if seg_len2 == 0:
            continue
        t = max(0.0, min(1.0, ((wx - x1) * dx + (wy - y1) * dy) / seg_len2))
        cx, cy = x1 + t * dx, y1 + t * dy
        dist = ((wx - cx) ** 2 + (wy - cy) ** 2) ** 0.5
        if dist < best_dist:
            best_dist = dist
            best = (i + 1, [cx, cy])
    return best
