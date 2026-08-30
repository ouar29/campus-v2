import asyncio
from pathlib import Path

from campus_app import CampusApp
from import_cps import _load_json_lenient, convert


class FakeSelect:
    def __init__(self):
        self.options = None
        self.value = None

    def set_options(self, options):
        self.options = options


class FakeList:
    def refresh(self):
        return None


class FakeDialog:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeFile:
    def __init__(self, name, content):
        self.name = name
        self._content = content

    async def read(self):
        return self._content


class FakeEvent:
    def __init__(self, name, content):
        self.file = FakeFile(name, content)


def test_lenient_loader_handles_malformed_sample_cps():
    data = _load_json_lenient("samples/campus.cps")
    assert data["name"] == "Site"
    assert len(data["buildings"]) >= 2

    campus, skipped = convert("samples/campus.cps")
    assert campus.name == "Site"
    assert skipped >= 0


def test_import_replaces_model_and_refreshes_selection(monkeypatch, tmp_path):
    import nicegui.ui as ui

    monkeypatch.setattr(ui, "notify", lambda *args, **kwargs: None)

    app = CampusApp.__new__(CampusApp)
    app.campus = type("CampusState", (), {"name": "Ancien", "buildings": []})()
    app.data_path = tmp_path / "data.json"
    app.controller = None
    app.campus_service = None
    app.floor_service = None
    app.room_service = None
    app.state = {"building": None, "floor": None}
    app.building_select = FakeSelect()
    app.floor_select = FakeSelect()
    app.room_list = FakeList()
    app.version_info = FakeList()
    app.plan_container = None
    app.save = lambda: None

    sample_path = Path("samples/louvre_grand_site.cps")
    dialog = FakeDialog()

    asyncio.run(app._on_cps_import(FakeEvent(sample_path.name, sample_path.read_bytes()), dialog))

    assert app.campus.name == "Grand Site Louvre"
    assert len(app.campus.buildings) == 2
    assert app.building_select.value == app.state["building"].id
    assert app.floor_select.value == app.state["floor"].id
    assert dialog.closed is True


def test_welcome_is_offered_only_while_the_campus_is_empty(tmp_path):
    """Le critère est le campus vide, pas l'absence de data.json.

    `get_data_path()` recrée le fichier dès le premier démarrage : se fier à
    son absence ne proposerait l'accueil qu'une seule fois.
    """
    from model import Campus

    app = CampusApp.__new__(CampusApp)
    app.campus = Campus(id="campus-1", name="Campus")
    assert app.should_offer_welcome() is True

    app.campus.add_building("Bâtiment A")
    assert app.should_offer_welcome() is False


def test_renaming_the_campus_also_renames_its_session(tmp_path):
    """L'étiquette de session vient du fichier importé, pas du modèle : sans
    synchronisation, le sélecteur garderait l'ancien nom de fichier."""
    from controller import CampusController
    from model import Campus

    campus = Campus(id="campus-1", name="Site")
    app = CampusApp.__new__(CampusApp)
    app.campus = campus
    app.controller = CampusController(campus, str(tmp_path / "data.json"))
    app.sessions = [{"key": "session-1", "label": "site3", "campus": campus}]
    app.current_session_key = "session-1"
    app.session_select = FakeSelect()
    app.campus_name_input = None

    app.rename_campus("Campus Nord")

    assert campus.name == "Campus Nord"
    assert app.sessions[0]["label"] == "Campus Nord"
    assert app.session_select.options == {"session-1": "Campus Nord"}
    assert app.session_select.value == "session-1"


def test_renaming_the_campus_to_an_empty_name_is_refused(tmp_path, monkeypatch):
    import nicegui.ui as ui

    from controller import CampusController
    from model import Campus

    monkeypatch.setattr(ui, "notify", lambda *args, **kwargs: None)

    campus = Campus(id="campus-1", name="Site")
    app = CampusApp.__new__(CampusApp)
    app.campus = campus
    app.controller = CampusController(campus, str(tmp_path / "data.json"))
    app.sessions = [{"key": "session-1", "label": "Site", "campus": campus}]
    app.current_session_key = "session-1"
    app.session_select = FakeSelect()
    app.campus_name_input = None

    app.rename_campus("")

    assert campus.name == "Site"
