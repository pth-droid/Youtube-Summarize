"""Customized slide looks: what is kept, how it reaches every deck in the look, and the look editor's preview."""
import re

from fastapi.testclient import TestClient

from distill import share
from distill.app import create_app
from distill.looks import (BODY_FONTS, COLOR_TOKENS, DISPLAY_FONTS, PREVIEW_SCRIPT, SLIDE_THEMES, designed_looks, font_stack,
                           look_blocks, look_changes, look_css, look_preview, with_custom_look)
from distill.renderer import render_lecture
from distill.storage import Store
from tests_app.learning_fixture import fixture
from tests_app.test_lecture import plan, slide
from tests_app.test_share import made

BRICOLAGE = 'font-family:"Bricolage Grotesque";src:url(data:font/woff2;base64,'


def test_every_look_is_read_whole_and_its_type_choices_come_from_the_looks():
    for look, designed in designed_looks().items():
        for mode in ("light", "dark"):
            assert set(designed[mode]) == set(COLOR_TOKENS), (look, mode)
            assert all(re.fullmatch(r"#[0-9a-f]{6}", colour) for colour in designed[mode].values()), (look, mode)
        assert designed["light"] != designed["dark"]
    # Each type choice is a stack a look was designed with; most looks' own type is among the choices.
    assert {font_stack("display", font) for font in DISPLAY_FONTS} == {looks["display"] for looks in designed_looks().values()}
    assert len({font_stack("sans", font) for font in BODY_FONTS}) == len(BODY_FONTS)


def test_only_what_differs_from_the_design_is_kept_and_laid_over_it():
    designed = designed_looks()["maroon"]
    sent = {"light": designed["light"] | {"accent": "#1F4E8C"}, "dark": dict(designed["dark"]), "display": "din", "sans": "bricolage"}
    changes = look_changes("maroon", sent)
    # Maroon's body type is Bricolage Grotesque already, so only the accent and the title type are kept.
    assert changes == {"light": {"accent": "#1f4e8c"}, "display": "din"}
    assert look_changes("maroon", {"light": designed["light"], "dark": designed["dark"]}) == {}
    css = look_css("maroon", changes | {"dark": {"surface": "#111111"}})
    assert css.startswith(":root[data-look=maroon]{--accent:#1f4e8c;--display:Bahnschrift")
    # Dark colours stay on screen, like the look's own, so print keeps the light version.
    assert css.endswith("@media screen{:root[data-look=maroon][data-theme=dark]{--surface:#111111}}")


def test_a_deck_shows_its_look_as_designed_today_with_the_saved_changes_and_a_preview_can_show_another_look():
    page = '<!doctype html>\n<html lang="vi" data-look="maroon"><head><style>x</style></head><body><p>slide</p></body></html>'
    custom = {"maroon": {"light": {"accent": "#1f4e8c"}}, "navy": {"light": {"ink": "#000000"}}}
    shown = with_custom_look(page, custom)
    # A deck made before the look changed shows it as designed today, with its font, then the saved changes, then print.
    style = shown[shown.index('<style id="look">'):shown.index("</head>")]
    assert style.index(BRICOLAGE) < style.index(look_blocks()["maroon"]) < style.index(":root[data-look=maroon]{--accent:#1f4e8c}")
    assert style.endswith("@media print{:root[data-look]{--paper:var(--surface)}}</style>")
    assert "--accent:#1f4e8c" not in with_custom_look(page, {"navy": custom["navy"]})
    assert BRICOLAGE not in with_custom_look(page.replace("maroon", "forest"), {})  # forest names installed fonts only
    assert with_custom_look("<html><head></head></html>", custom) == "<html><head></head></html>"  # a learning page
    # The editor's preview: the deck in navy, navy's saved changes, the type being tried, and the colour script.
    preview = look_preview(page, custom, "navy", {"display": "sitka", "sans": ""})
    assert 'data-look="navy"' in preview and "--ink:#000000" in preview and '"Sitka Heading"' in preview
    assert preview.endswith(PREVIEW_SCRIPT + "</body></html>")


def test_saved_looks_restyle_every_deck_in_the_look_as_it_is_shown_exported_or_shared(tmp_path, monkeypatch):
    app = create_app(tmp_path)
    store: Store = app.state.store
    deck, page = made(store, "lecture", look="maroon"), made(store, "page")
    monkeypatch.setattr(share, "tailscale_link", lambda port: {"installed": False, "connected": False, "url": None, "command": ""})
    with TestClient(app, base_url="http://127.0.0.1") as client:
        headers = {"x-distill": app.state.csrf_token}
        looks = client.get("/api/looks").json()
        assert [look["id"] for look in looks["looks"]] == list(SLIDE_THEMES) and looks["tokens"] == list(COLOR_TOKENS)
        assert {font["id"] for font in looks["fonts"]["display"]} == set(DISPLAY_FONTS)
        assert "--accent:#1f4e8c" not in client.get(f"/api/generations/{deck}/page").text

        designed = designed_looks()["maroon"]
        sent = {"light": designed["light"] | {"accent": "#1f4e8c"}, "dark": designed["dark"] | {"surface": "#111111"}, "display": "din"}
        assert client.put("/api/looks/maroon", json=sent).status_code == 403  # writes need the app's token
        saved = client.put("/api/looks/maroon", json=sent, headers=headers).json()
        maroon = next(look for look in saved["looks"] if look["id"] == "maroon")
        assert maroon["changes"] == {"light": {"accent": "#1f4e8c"}, "dark": {"surface": "#111111"}, "display": "din"}
        swatch = next(look for look in client.get("/api/settings").json()["looks"] if look["id"] == "maroon")
        assert swatch["custom"] and swatch["tokens"]["accent"] == "#1f4e8c" and swatch["tokens"]["display"].startswith("Bahnschrift")
        assert swatch == next(look for look in saved["swatches"] if look["id"] == "maroon")

        # The deck was made before the change; it shows the change when it is opened, exported or shared.
        opened = client.get(f"/api/generations/{deck}/page")
        assert "--accent:#1f4e8c" in opened.text and opened.headers["content-security-policy"].startswith("sandbox allow-scripts")
        assert "--accent:#1f4e8c" in client.get(f"/api/generations/{deck}/export").text
        assert "--accent:#1f4e8c" not in client.get(f"/api/generations/{page}/page").text
        assert client.post(f"/api/generations/{deck}/share", headers=headers).status_code == 200
        assert "--accent:#1f4e8c" in client.get(f"/api/generations/{deck}/share/download").text

        # The editor's preview shows any deck in any look, sandboxed, with the type being tried.
        preview = client.get(f"/api/looks/forest/preview/{deck}", params={"display": "book", "sans": ""})
        assert preview.status_code == 200 and 'data-look="forest"' in preview.text and PREVIEW_SCRIPT in preview.text
        assert '"Iowan Old Style"' in preview.text and preview.headers["content-security-policy"].startswith("sandbox allow-scripts")
        assert client.get(f"/api/looks/forest/preview/{page}").status_code == 409
        assert client.get(f"/api/looks/forest/preview/{deck}", params={"display": "comic"}).status_code == 422

        # Only colours as hex codes and the offered type; unknown looks are not found.
        for bad in ({"light": {"accent": "red"}}, {"light": {"accent": "#1f4e8c;}body{x:y"}}, {"light": {"glow": "#ffffff"}}, {"display": "comic"}):
            assert client.put("/api/looks/maroon", json=bad, headers=headers).status_code == 422, bad
        assert client.put("/api/looks/neon", json={}, headers=headers).status_code == 404

        # Reset puts the look back as designed for every deck.
        reset = client.delete("/api/looks/maroon", headers=headers).json()
        assert next(look for look in reset["looks"] if look["id"] == "maroon")["changes"] == {}
        assert "--accent:#1f4e8c" not in client.get(f"/api/generations/{deck}/page").text
        assert store.custom_looks() == {}


def test_a_maroon_deck_carries_bricolage_grotesque_once_wherever_it_is_opened(tmp_path):
    source, knowledge, _ = fixture()
    lecture = plan(slide(), slide("steps", title="In order"))
    maroon = render_lecture(source, knowledge, lecture, tmp_path / "maroon.html", theme="maroon").read_text(encoding="utf-8")
    forest = render_lecture(source, knowledge, lecture, tmp_path / "forest.html", theme="forest").read_text(encoding="utf-8")
    phone = render_lecture(source, knowledge, lecture, tmp_path / "phone.html", theme="maroon", phone=True).read_text(encoding="utf-8")
    # The font is inside the file, Latin and Vietnamese, and only in a look whose type names it.
    assert maroon.count(BRICOLAGE) == 1 and phone.count(BRICOLAGE) == 1 and BRICOLAGE not in forest
    assert '--display:"Bricolage Grotesque"' in maroon and '--sans:"Bricolage Grotesque"' in maroon
    # Shown again, the deck keeps its one copy; a forest deck whose type is changed to Bricolage gains it.
    assert with_custom_look(maroon, {}).count(BRICOLAGE) == 1
    assert with_custom_look(forest, {"forest": {"display": "bricolage"}}).count(BRICOLAGE) == 1
