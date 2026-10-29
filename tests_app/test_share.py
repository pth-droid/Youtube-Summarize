"""Share to phone: the phone copy of a deck, its tailnet route, the download, and reading Tailscale's serve setup."""
import json
import re
import subprocess
from types import SimpleNamespace

from fastapi.testclient import TestClient

from distill import share
from distill.app import create_app
from distill.pipeline import Pipeline
from distill.renderer import render_lecture
from distill.storage import Store
from tests_app.learning_fixture import fixture
from tests_app.test_learning import SemanticFixtureProvider
from tests_app.test_lecture import plan, slide

TAILNET = "https://pc.example.ts.net"


def made(store: Store, output_format: str, look: str = "navy") -> str:
    """A finished generation, made the way the worker makes one."""
    source, _, _ = fixture()
    job = store.create_job({"kind": "import", "preferences": store.settings()})
    preferences = {"language": "en", "output_format": output_format, "slide_theme": look}
    result = Pipeline(SemanticFixtureProvider()).run(source, preferences, store.artifact_dir(job["id"]))
    return store.publish_generation(job["id"], result)["id"]


def test_phone_copy_presents_at_every_width_and_keeps_only_the_slide(tmp_path):
    source, knowledge, _ = fixture()
    lecture = plan(slide(), slide("steps", title="In order"))
    deck = render_lecture(source, knowledge, lecture, tmp_path / "deck.html", theme="slate").read_text(encoding="utf-8")
    phone = render_lecture(source, knowledge, lecture, tmp_path / "phone.html", theme="slate", phone=True).read_text(encoding="utf-8")
    # The deck for the computer keeps its stacked list for narrow screens and has no phone controls.
    assert 'data-mode="phone"' not in deck and "(min-width:761px)" in deck and 'id="controls-toggle"' not in deck
    # The phone copy draws the canvas at every width: an iPhone held sideways is 734px wide. No narrow-screen rule applies.
    assert 'data-look="slate" data-mode="phone"' in phone
    assert "(min-width:761px)" not in phone and not re.search(r"\(max-width:\s*(?!0px)\d+px\)", phone)
    assert 'id="controls-toggle"' in phone and 'class="rotate-hint"' in phone
    assert "viewport-fit=cover" in phone and 'name="apple-mobile-web-app-capable" content="yes"' in phone
    assert phone.count('class="slide-frame"') == deck.count('class="slide-frame"')


def test_share_renders_a_phone_copy_that_the_tailnet_reads_only_at_share(tmp_path, monkeypatch):
    app = create_app(tmp_path)
    store: Store = app.state.store
    deck, page = made(store, "lecture"), made(store, "page")
    monkeypatch.setattr(share, "tailscale_link", lambda port: {"installed": True, "connected": True, "url": f"{TAILNET}/distill/share",
                                                               "command": f"tailscale serve --bg --set-path /distill/share http://127.0.0.1:{port}/share"})
    with TestClient(app, base_url="http://127.0.0.1") as local, TestClient(app, base_url=TAILNET) as tailnet:
        headers = {"x-distill": app.state.csrf_token}
        # Nothing is shared until the owner shares it.
        assert tailnet.get(f"/share/{deck}").status_code == 404
        assert local.post(f"/api/generations/{deck}/share").status_code == 403
        shared = local.post(f"/api/generations/{deck}/share", headers=headers).json()
        assert shared["url"] == f"{TAILNET}/distill/share/{deck}" and shared["qr"].startswith("data:image/svg+xml")
        assert shared["download"] == f"/api/generations/{deck}/share/download"
        assert local.post(f"/api/generations/{page}/share", headers=headers).status_code == 409

        # The tailnet reads the phone copy, sandboxed like any saved deck, in the deck's look.
        opened = tailnet.get(f"/share/{deck}")
        assert opened.status_code == 200 and 'data-mode="phone"' in opened.text and 'data-look="navy"' in opened.text
        assert opened.headers["content-security-policy"].startswith("sandbox allow-scripts")
        # Everything else stays local: the API, the saved deck itself, and any write.
        for path in ("/api/settings", "/api/library", f"/api/generations/{deck}/page", f"/api/generations/{deck}/share/download", "/"):
            assert tailnet.get(path).status_code == 403, path
        assert tailnet.post(f"/share/{deck}").status_code == 403
        assert tailnet.get("/share/not-an-id").status_code == 404 and tailnet.get(f"/share/{page}").status_code == 404

        # The download is the same phone copy, as a file.
        download = local.get(f"/api/generations/{deck}/share/download")
        assert download.status_code == 200 and "lecture-slides-phone-" in download.headers["content-disposition"]
        assert 'data-mode="phone"' in download.text


def test_tailscale_link_finds_the_serve_path_that_reaches_this_port(monkeypatch):
    serve = {"Web": {"pc.example.ts.net:443": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:8765"}, "/share": {"Proxy": "http://127.0.0.1:8766"},
                                                            "/distill/share": {"Proxy": "http://127.0.0.1:8767/share"}}},
                     "pc.example.ts.net:8443": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:9000/share"}}}}}

    def run(args, **_kwargs):
        body = {"BackendState": "Running"} if args[1] == "status" else serve
        return SimpleNamespace(returncode=0, stdout=json.dumps(body))

    monkeypatch.setattr(share, "tailscale_command", lambda: "tailscale")
    monkeypatch.setattr(subprocess, "run", run)
    # Another app's /share on the same name is not this app's.
    assert share.tailscale_link(8767)["url"] == "https://pc.example.ts.net/distill/share"
    assert share.tailscale_link(9000)["url"] == "https://pc.example.ts.net:8443"
    missing = share.tailscale_link(8770)
    assert missing["connected"] and missing["url"] is None
    assert missing["command"] == "tailscale serve --bg --set-path /distill/share http://127.0.0.1:8770/share"
    monkeypatch.setattr(share, "tailscale_command", lambda: None)
    assert share.tailscale_link(8767) == {"installed": False, "connected": False, "url": None, "command": missing["command"].replace("8770", "8767")}
