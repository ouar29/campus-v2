import pytest

from model import Campus
from services.campus_service import CampusService
from services.floor_service import FloorGeometryEditor, FloorService
from services.room_service import RoomService


def test_campus_service_create_building():
    campus = Campus(id="campus-1", name="Campus")
    service = CampusService(campus)

    building = service.create_building("Bâtiment X")

    assert building.name == "Bâtiment X"
    assert len(campus.buildings) == 1


def test_floor_service_create_floor_validates_polygon():
    campus = Campus(id="campus-1", name="Campus")
    building = campus.add_building("Bâtiment Y")
    service = FloorService(campus)

    floor = service.create_floor(building, "RDC", [[0.0, 0.0], [4.0, 0.0], [4.0, 2.0], [0.0, 2.0]], level=0)

    assert floor.name == "RDC"
    assert floor.level == 0
    assert len(building.floors) == 1

    with pytest.raises(ValueError):
        service.create_floor(building, "Erreur", [[0.0, 0.0], [1.0, 1.0]], level=1)


def test_room_service_create_room_and_validates_capacity():
    campus = Campus(id="campus-1", name="Campus")
    building = campus.add_building("Bâtiment Z")
    floor = building.add_floor("1", [[0.0, 0.0], [5.0, 0.0], [5.0, 3.0], [0.0, 3.0]], level=1)
    service = RoomService(campus)

    room = service.create_room(floor, "Salle A", 18, [1.5, 1.5])

    assert room.name == "Salle A"
    assert room.capacity == 18
    assert room.position == [1.5, 1.5]
    assert len(floor.rooms) == 1

    with pytest.raises(ValueError):
        service.create_room(floor, "Salle invalide", 0, [0.0, 0.0])


def test_campus_service_create_modular_building():
    campus = Campus(id="campus-1", name="Campus")
    service = CampusService(campus)

    building = service.create_modular_building(
        "Tour A", width=30, depth=12, floor_count=4, lowest_level=-1, position=[100.0, 50.0]
    )

    assert building.position == [100.0, 50.0]
    assert [f.level for f in building.floors] == [-1, 0, 1, 2]
    assert [f.name for f in building.floors] == ["Sous-sol -1", "RDC", "1er étage", "2e étage"]
    expected = [[0.0, 0.0], [30.0, 0.0], [30.0, 12.0], [0.0, 12.0]]
    assert all(floor.polygon == expected for floor in building.floors)
    # Chaque étage a sa propre copie : éditer un contour n'en déforme pas un autre.
    building.floors[0].polygon[0][0] = 5.0
    assert building.floors[1].polygon[0][0] == 0.0


def test_campus_service_create_modular_building_validates_inputs():
    campus = Campus(id="campus-1", name="Campus")
    service = CampusService(campus)

    with pytest.raises(ValueError):
        service.create_modular_building("Sans largeur", width=0, depth=10)
    with pytest.raises(ValueError):
        service.create_modular_building("Sans niveau", width=10, depth=10, floor_count=0)
    with pytest.raises(ValueError):
        service.create_modular_building("  ", width=10, depth=10)
    assert campus.buildings == []


def test_campus_service_resize_building_scales_floors_and_rooms():
    campus = Campus(id="campus-1", name="Campus")
    service = CampusService(campus)
    building = service.create_modular_building("Tour B", width=20, depth=10, floor_count=2)
    room = building.floors[0].add_room("Salle A", 10, [10.0, 5.0])

    service.resize_building(building, 40, 5)

    assert building.floors[0].polygon == [[0.0, 0.0], [40.0, 0.0], [40.0, 5.0], [0.0, 5.0]]
    assert building.floors[1].polygon == [[0.0, 0.0], [40.0, 0.0], [40.0, 5.0], [0.0, 5.0]]
    # La salle était au centre du plateau, elle y reste.
    assert room.position == [20.0, 2.5]


def test_campus_service_resize_building_rejects_building_without_polygon():
    campus = Campus(id="campus-1", name="Campus")
    service = CampusService(campus)
    building = service.create_building("Bâtiment vide")

    with pytest.raises(ValueError):
        service.resize_building(building, 10, 10)


SQUARE = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]


def _floor_with_square():
    campus = Campus(id="campus-1", name="Campus")
    building = campus.add_building("Bâtiment")
    return building.add_floor("RDC", [list(p) for p in SQUARE], level=0)


def test_geometry_editor_undoes_vertex_moves_in_reverse_order():
    floor = _floor_with_square()
    editor = FloorGeometryEditor()
    editor.begin(floor)

    editor.push(floor)
    floor.polygon[2] = [20.0, 10.0]
    editor.push(floor)
    floor.polygon.pop(0)

    assert editor.undo(floor) is True
    assert floor.polygon == [[0.0, 0.0], [10.0, 0.0], [20.0, 10.0], [0.0, 10.0]]
    assert editor.undo(floor) is True
    assert floor.polygon == SQUARE
    assert editor.undo(floor) is False


def test_geometry_editor_discards_snapshot_when_nothing_moved():
    floor = _floor_with_square()
    editor = FloorGeometryEditor()
    editor.begin(floor)

    # Un clic sur un sommet sans déplacement : le point de reprise est jeté.
    editor.push(floor)
    assert editor.discard_if_unchanged(floor) is True
    assert editor.can_undo(floor) is False

    editor.push(floor)
    floor.polygon[0] = [1.0, 1.0]
    assert editor.discard_if_unchanged(floor) is False
    assert editor.can_undo(floor) is True


def test_geometry_editor_reset_returns_to_session_start_and_is_undoable():
    floor = _floor_with_square()
    editor = FloorGeometryEditor()
    editor.begin(floor)

    editor.push(floor)
    floor.polygon.append([5.0, 15.0])
    edited = [list(p) for p in floor.polygon]

    assert editor.reset(floor) is True
    assert floor.polygon == SQUARE
    assert editor.can_reset(floor) is False
    # Un « rétablir » malencontreux se rattrape comme n'importe quel geste.
    assert editor.undo(floor) is True
    assert floor.polygon == edited


def test_geometry_editor_session_is_scoped_to_one_floor():
    floor = _floor_with_square()
    other = _floor_with_square()
    editor = FloorGeometryEditor()
    editor.begin(floor)
    editor.push(floor)
    floor.polygon.pop()

    # Passer sur un autre étage repart de zéro : aucune annulation croisée.
    assert editor.can_undo(other) is False
    assert editor.undo(other) is False
    editor.ensure_session(other)
    assert editor.can_undo(floor) is False


def test_geometry_editor_caps_the_undo_stack():
    floor = _floor_with_square()
    editor = FloorGeometryEditor(max_steps=3)
    editor.begin(floor)
    for i in range(6):
        editor.push(floor)
        floor.polygon[0] = [float(i), 0.0]

    assert len(editor.stack) == 3
    for _ in range(3):
        assert editor.undo(floor) is True
    assert editor.undo(floor) is False


def test_campus_service_rename_campus_trims_and_rejects_empty():
    campus = Campus(id="campus-1", name="Ancien nom")
    service = CampusService(campus)

    assert service.rename_campus("  Campus Nord  ") == "Campus Nord"
    assert campus.name == "Campus Nord"

    # Le nom part dans le champ `name` du .cps exporté : le vider casserait
    # l'export et le nom de fichier proposé.
    with pytest.raises(ValueError):
        service.rename_campus("   ")
    assert campus.name == "Campus Nord"


def test_room_predicates_used_by_the_predefined_filters():
    from model import PENDING_BUILDING_NAME
    from services.room_service import (
        has_no_gestionnaire,
        has_suspicious_capacity,
        is_awaiting_placement,
        is_unavailable,
    )

    campus = Campus(id="campus-1", name="Campus")
    building = campus.add_building("Bâtiment A")
    floor = building.add_floor("RDC", SQUARE, level=0)
    room = floor.add_room("Salle A", 10, [1.0, 1.0])

    # Une salle saine ne remonte dans aucun filtre.
    assert is_unavailable(room) is False
    assert has_suspicious_capacity(room) is False
    assert is_awaiting_placement(building) is False
    # ... sauf « sans gestionnaire », tant qu'aucun n'est assigné.
    assert has_no_gestionnaire(room) is True

    room.gestionnaire_ids = ["gest-1"]
    assert has_no_gestionnaire(room) is False

    # `available` vient du .cps d'origine, conservé dans extra.
    room.extra["available"] = False
    assert is_unavailable(room) is True

    room.capacity = 0
    assert has_suspicious_capacity(room) is True

    placeholder = campus.add_building(PENDING_BUILDING_NAME)
    assert is_awaiting_placement(placeholder) is True


def test_predefined_filters_combine_cumulatively():
    """Deux filtres actifs restreignent, ils ne s'additionnent pas."""
    from ui.room_table_view import PREDEFINED_FILTERS

    campus = Campus(id="campus-1", name="Campus")
    building = campus.add_building("Bâtiment A")
    floor = building.add_floor("RDC", SQUARE, level=0)
    indisponible = floor.add_room("Indispo", 10, [1.0, 1.0])
    indisponible.extra["available"] = False
    indisponible.gestionnaire_ids = ["gest-1"]
    floor.add_room("Sans gestionnaire", 10, [2.0, 2.0])

    predicates = {key: predicate for key, _, _, predicate in PREDEFINED_FILTERS}

    def matching(active):
        return [
            room.name
            for room in floor.rooms
            if all(predicates[key](building, floor, room) for key in active)
        ]

    assert matching({"unavailable"}) == ["Indispo"]
    assert matching({"no_gestionnaire"}) == ["Sans gestionnaire"]
    # Aucune salle n'est à la fois indisponible et sans gestionnaire.
    assert matching({"unavailable", "no_gestionnaire"}) == []
