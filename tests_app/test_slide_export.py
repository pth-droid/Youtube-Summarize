"""Export: finding a browser, the arguments of each headless launch, and the files the export route returns. No real browser runs."""
import io
import re
import sys
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from distill import slide_export
from distill.app import create_app
from distill.renderer import lecture_page
from tests_app.figure_fixture import figure_fixture
from tests_app.test_deck_structure import plan
from tests_app.test_share import made


def test_the_browser_is_found_from_the_environment_then_the_usual_folders_then_the_path(tmp_path, monkeypatch):
    program = tmp_path / "msedge.exe"
    program.write_text("", encoding="utf-8")
    monkeypatch.setenv("DISTILL_BROWSER", f'"{program}"')
    assert slide_export.find_browser() == str(program)
    monkeypatch.setenv("DISTILL_BROWSER", str(tmp_path / "missing.exe"))
    with pytest.raises(slide_export.ExportError, match="DISTILL_BROWSER") as named:
        slide_export.find_browser()
    assert named.value.status == 424
    monkeypatch.delenv("DISTILL_BROWSER")
    folder = tmp_path / "Microsoft" / "Edge" / "Application"
    folder.mkdir(parents=True)
    (folder / "msedge.exe").write_text("", encoding="utf-8")
    monkeypatch.setenv("ProgramFiles(x86)", str(tmp_path))
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "none"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "none"))
    assert slide_export.find_browser() == str(folder / "msedge.exe")
    (folder / "msedge.exe").unlink()
    monkeypatch.setattr(slide_export.shutil, "which", lambda name: str(program) if name == "chrome" else None)
    assert slide_export.find_browser() == str(program)
    monkeypatch.setattr(slide_export.shutil, "which", lambda name: None)
    with pytest.raises(slide_export.ExportError, match="Edge or Google Chrome") as none:
        slide_export.find_browser()
    assert none.value.status == 424


def test_each_launch_prints_one_pdf_or_screenshots_one_slide_in_its_own_profile(tmp_path):
    page, profile = tmp_path / "deck.html", tmp_path / "profile"
    pdf = slide_export.pdf_command("edge", profile, page, tmp_path / "out.pdf")
    assert pdf[0] == "edge" and "--headless=new" in pdf and f"--user-data-dir={profile}" in pdf
    assert f"--print-to-pdf={tmp_path / 'out.pdf'}" in pdf and "--no-pdf-header-footer" in pdf
    assert any(flag.startswith("--virtual-time-budget=") for flag in pdf) and pdf[-1] == page.resolve().as_uri()
    assert slide_export.pdf_command("edge", profile, page, tmp_path / "out.pdf", 4)[-1].endswith("deck.html#slide-4")
    png = slide_export.png_command("edge", profile, page, tmp_path / "s.png", 7, 2)
    assert "--window-size=1280,720" in png and "--force-device-scale-factor=2" in png and f"--screenshot={tmp_path / 's.png'}" in png
    assert png[-1].endswith("deck.html#slide-7") and "--print-to-pdf" not in " ".join(png)


def test_the_deck_page_is_prepared_with_the_slide_at_its_own_size_and_a_light_look():
    source, knowledge, _ = figure_fixture()
    page = lecture_page(source, knowledge, plan(), theme="maroon")
    prepared = slide_export.export_page(page)
    assert prepared.count('<style id="export">') == 1 and "@page{size:1280px 720px;margin:0}" in prepared
    assert 'dataset.theme="light"' in prepared and 'dataset.theme="dark"' in slide_export.export_page(page, "dark")
    assert slide_export.slide_count(page) == page.count('class="slide-frame"') == 13
    only = slide_export.only_slide(page, "0.1")
    assert re.search(r"location\.hash='#slide-7'", only) and '.slide-frame:not([data-slide="0.1"])' in only
    with pytest.raises(slide_export.ExportError, match="not in the deck"):
        slide_export.only_slide(page, "9.9")


def test_a_launch_that_draws_nothing_or_hangs_is_an_error_the_person_can_read(tmp_path, monkeypatch):
    output = tmp_path / "out.png"
    with pytest.raises(slide_export.ExportError, match="did not draw"):
        slide_export.launch([sys.executable, "-c", "pass"], output)
    output.write_bytes(b"png")
    assert slide_export.launch([sys.executable, "-c", "pass"], output) == b"png"
    monkeypatch.setattr(slide_export, "TIMEOUT", 1)
    with pytest.raises(slide_export.ExportError, match="too long") as slow:
        slide_export.launch([sys.executable, "-c", "import time; time.sleep(30)"], output)
    assert slow.value.status == 504
    with pytest.raises(slide_export.ExportError, match="could not start"):
        slide_export.launch([str(tmp_path / "nothing.exe")], output)


def test_the_export_route_returns_a_pdf_a_picture_or_a_zip_of_pictures(tmp_path, monkeypatch):
    launches = []

    def fake(arguments, output):
        launches.append([part for part in arguments if part.startswith("--") or part.startswith("file:")])
        data = b"%PDF fake" if output.suffix == ".pdf" else b"\x89PNG fake " + output.stem.encode()
        output.write_bytes(data)
        return data

    monkeypatch.setattr(slide_export, "launch", fake)
    monkeypatch.setenv("DISTILL_BROWSER", sys.executable)
    app = create_app(tmp_path)
    deck, page = made(app.state.store, "lecture"), made(app.state.store, "page")
    with TestClient(app, base_url="http://127.0.0.1") as client:
        url = f"/api/generations/{deck}/slides/export"
        count = client.get(f"/api/generations/{deck}/page").text.count('class="slide-frame"')
        everything = client.get(url, params={"format": "pdf"})
        assert everything.status_code == 200 and everything.content == b"%PDF fake" and everything.headers["content-type"] == "application/pdf"
        assert everything.headers["content-disposition"].endswith('.pdf"') and len(launches) == 1 and not launches[0][-1].count("#")
        one = client.get(url, params={"format": "pdf", "slide": 2})
        assert "slide-02.pdf" in one.headers["content-disposition"] and launches[-1][-1].endswith("#slide-2")
        launches.clear()
        picture = client.get(url, params={"format": "png", "slide": 3, "scale": 3})
        assert picture.headers["content-type"] == "image/png" and picture.content.startswith(b"\x89PNG") and "slide-03.png" in picture.headers["content-disposition"]
        assert "--force-device-scale-factor=3" in launches[0] and len(launches) == 1
        launches.clear()
        archive = client.get(url, params={"format": "png", "slide": "all", "scale": 2})
        assert archive.headers["content-type"] == "application/zip" and len(launches) == count
        names = zipfile.ZipFile(io.BytesIO(archive.content)).namelist()
        assert len(names) == count and names == sorted(names) and names[0].endswith("-01.png")
        # Slides that are not in the deck, unknown formats and scales, and a page that is not a deck are refused.
        assert client.get(url, params={"format": "png", "slide": count + 1}).status_code == 422
        assert client.get(url, params={"format": "gif"}).status_code == 422
        assert client.get(url, params={"format": "png", "scale": 4}).status_code == 422
        assert client.get(f"/api/generations/{page}/slides/export", params={"format": "pdf"}).status_code == 409
        monkeypatch.setenv("DISTILL_BROWSER", str(tmp_path / "gone.exe"))
        missing = client.get(url, params={"format": "pdf"})
        assert missing.status_code == 424 and "DISTILL_BROWSER" in missing.json()["detail"]


def test_hidden_slides_are_not_exported(tmp_path, monkeypatch):
    source, knowledge, _ = figure_fixture()
    lecture = plan()
    lecture.parts[0].slides[0].hidden = True
    assert slide_export.slide_count(lecture_page(source, knowledge, lecture)) == slide_export.slide_count(lecture_page(source, knowledge, plan())) - 1
