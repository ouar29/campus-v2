from datetime import date
import asyncio

from campus_app import write_default_campus
from model import Campus
from rendering import campus_map_parts
from ui.uploads import read_uploaded_file
from export_cps import export_campus


class FakeUploadFile:
    def __init__(self, name: str, data: bytes):
        self.name = name
        self._data = data

    def read(self):
        return self._data


class FakeUploadEvent:
    def __init__(self, name: str, data: bytes):
        self.file = FakeUploadFile(name, data)


def test_campus_map_preview_renders_without_error():
    campus = Campus(id="campus-1", name="Campus Test")
    building = campus.add_building("Bâtiment A")
    building.add_floor("RDC", [[0.0, 0.0], [8.0, 0.0], [8.0, 5.0], [0.0, 5.0]], level=0)

    html, js = campus_map_parts(campus)

    assert "<svg" in html
    assert "campusmap-svg-" in html
    assert "ResizeObserver" in js


def test_read_uploaded_file_handles_nicegui_upload_event():
    event = FakeUploadEvent("campus.cps", b'{"name": "Test"}')

    result = asyncio.run(read_uploaded_file(event))

    assert result is not None
    assert result[0] == "campus.cps"
    assert result[1] == b'{"name": "Test"}'
    

def test_export_campus_sets_version_to_today_date():
    campus = Campus(id="campus-1", name="Campus Test")
    campus.add_building("Bâtiment A")

    exported = export_campus(campus)

    assert exported["version"] == date.today().isoformat()


def test_create_building_and_floor():
    campus = Campus(id="campus-1", name="Campus Test")
    building = campus.add_building("Bâtiment A")
    floor = building.add_floor("RDC", [[0.0, 0.0], [10.0, 0.0], [10.0, 5.0], [0.0, 5.0]], level=0)

    assert len(campus.buildings) == 1
    assert campus.buildings[0].name == "Bâtiment A"
    assert floor.level == 0
    assert len(floor.polygon) == 4


def test_create_room_and_capacity():
    campus = Campus(id="campus-1", name="Campus Test")
    building = campus.add_building("Bâtiment B")
    floor = building.add_floor("1", [[0.0, 0.0], [6.0, 0.0], [6.0, 4.0], [0.0, 4.0]], level=1)
    room = floor.add_room("Salle 101", 24, [2.0, 2.0])

    assert room.name == "Salle 101"
    assert room.capacity == 24
    assert room.position == [2.0, 2.0]
    assert len(floor.rooms) == 1


def test_save_and_load_round_trip(tmp_path):
    campus = Campus(id="campus-1", name="Campus Test")
    building = campus.add_building("Bâtiment C")
    floor = building.add_floor("RDC", [[0.0, 0.0], [5.0, 0.0], [5.0, 3.0], [0.0, 3.0]], level=0)
    floor.add_room("Salle C1", 12, [1.5, 1.5])

    path = tmp_path / "campus.json"
    campus.save(path)
    loaded = Campus.load(path)

    assert loaded.name == "Campus Test"
    assert len(loaded.buildings) == 1
    assert loaded.buildings[0].floors[0].rooms[0].name == "Salle C1"
    assert loaded.buildings[0].floors[0].rooms[0].capacity == 12


def test_write_default_campus_produces_a_loadable_empty_campus(tmp_path):
    """Le campus par défaut sert de filet quand data.json manque : s'il cessait
    d'être chargeable, l'application planterait au démarrage au lieu d'être
    rattrapée."""
    path = tmp_path / "data.json"

    write_default_campus(path)
    campus = Campus.load(path)

    assert campus.buildings == []
    assert campus.gestionnaires == []
    assert campus.name


def test_modular_building_footprint_matches_position_and_size():
    from geometry import building_footprint, building_size
    from services.campus_service import CampusService

    campus = Campus(id="campus-1", name="Campus")
    building = CampusService(campus).create_modular_building(
        "Tour", width=25, depth=8, floor_count=3, position=[100.0, 40.0]
    )

    assert building_size(building) == (25.0, 8.0)
    # `position` est le coin bas-gauche de l'empreinte, comme pour les
    # contours importés d'un .cps (polygone dans le quadrant positif).
    assert building_footprint(building) == [
        [100.0, 40.0],
        [125.0, 40.0],
        [125.0, 48.0],
        [100.0, 48.0],
    ]


def test_iso_view_floors_are_thin_slabs_and_never_intersect():
    from iso_view import FLOOR_HEIGHT, SLAB_THICKNESS

    # L'épaisseur d'une dalle doit rester inférieure à l'espacement entre
    # niveaux, sinon les étages se traversent au lieu de s'empiler.
    assert 0 < SLAB_THICKNESS < FLOOR_HEIGHT


def test_iso_view_draws_floor_labels_above_every_slab():
    """Les niveaux étant serrés, une dalle masquerait l'étiquette du dessous."""
    from iso_view import build_overview_svg
    from services.campus_service import CampusService

    campus = Campus(id="campus-1", name="Campus")
    CampusService(campus).create_modular_building("Tour", 20, 10, floor_count=3)

    svg = build_overview_svg(campus)

    # La grille au sol est faite de <line>, donc tous les <polygon> du SVG
    # sont des faces d'étage : la dernière doit précéder la première
    # étiquette (l'ordre du document est l'ordre de peinture).
    assert svg.rindex("<polygon") < svg.index(">RDC<")
    for name in ("RDC", "1er étage", "2e étage"):
        assert f">{name}<" in svg


def test_packaged_app_starts_empty_when_no_data_is_bundled(tmp_path, monkeypatch):
    """Le bundle n'embarque plus de data.json : le premier lancement doit
    créer un campus vide dans le dossier utilisateur, pas planter."""
    import campus_app

    user_dir = tmp_path / "userdata"
    monkeypatch.setattr(campus_app.sys, "frozen", True, raising=False)
    monkeypatch.setattr(campus_app.platformdirs, "user_data_dir", lambda *a, **k: str(user_dir))
    monkeypatch.setattr(campus_app, "get_resource_path", lambda rel: tmp_path / "absent" / rel)

    path = campus_app.get_data_path()

    assert path == user_dir / "data.json"
    assert Campus.load(path).buildings == []


def test_renamed_campus_reaches_the_cps_export():
    """Le nom saisi dans la carte « Session » est bien celui du .cps produit."""
    from services.campus_service import CampusService

    campus = Campus(id="campus-1", name="Site")
    campus.add_building("Bâtiment A")
    CampusService(campus).rename_campus("Campus Nord")

    assert export_campus(campus)["name"] == "Campus Nord"


def test_palette_for_falls_back_to_dark_on_the_system_theme():
    from theme import DARK, LIGHT, palette_for

    assert palette_for(True) is DARK
    assert palette_for(False) is LIGHT
    # NiceGUI expose `None` pour « thème système » : le sombre reste le défaut.
    assert palette_for(None) is DARK


def test_svg_renderings_follow_the_requested_palette():
    """Les SVG sont générés côté serveur : sans palette explicite, ils
    resteraient indigo sur un thème clair (le défaut de départ)."""
    from iso_view import build_overview_svg
    from rendering import blank_background, floor_plan_content
    from theme import DARK, LIGHT

    campus = Campus(id="campus-1", name="Campus")
    building = campus.add_building("Bâtiment A")
    floor = building.add_floor("RDC", [[0.0, 0.0], [10.0, 0.0], [10.0, 5.0], [0.0, 5.0]], level=0)
    floor.add_room("Salle A", 10, [5.0, 2.5])

    light_plan = floor_plan_content(floor, 0.0, 0.0, 1.0, LIGHT)
    assert LIGHT.FLOOR_FILL in light_plan
    assert DARK.FLOOR_FILL not in light_plan
    assert LIGHT.TEXT_PRIMARY in light_plan

    # Le fond du plan est une image data URI : il doit suivre lui aussi.
    assert blank_background(10, 5, LIGHT) != blank_background(10, 5, DARK)

    light_iso = build_overview_svg(campus, 0.0, LIGHT)
    assert f"background:{LIGHT.ISO_BG}" in light_iso
    assert DARK.ISO_BG not in light_iso
