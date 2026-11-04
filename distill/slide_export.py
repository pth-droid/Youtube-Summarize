"""Slides as a PDF or as PNG pictures, drawn by the Edge or Chrome already on this computer.

The deck's saved page is prepared for the browser (every slide at the canvas's own 1280x720 size, no controls, no motion,
every build step shown) and printed headless: one launch prints all slides to a PDF with one 16:9 page each, and one launch per
slide takes a screenshot of it. Several pictures arrive together as a ZIP. The pages and pictures are made from the saved deck,
so hidden slides are left out, as they are when presenting, and nothing leaves this computer.
"""
from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

WIDTH, HEIGHT = 1280, 720
SCALES = (1, 2, 3)
PARALLEL = 3
TIMEOUT = 90  # seconds for one launch
# Page ready: fonts and the fit that shrinks long text finish within the virtual time the browser is given.
VIRTUAL_TIME = 5000
NO_BROWSER = ("Exporting needs Microsoft Edge or Google Chrome, and neither was found on this computer. Install one, or set the "
              "DISTILL_BROWSER environment variable to the path of its program, then try again.")

# Applied on top of the deck page, whatever the media: the slide at its own size at the top left of the page, with no
# controls, motion or waiting build steps. A slide asked for by #slide-N is the only one drawn.
EXPORT_CSS = """
.deck-bar,.deck-nav,.notes,dialog,.controls-toggle,.rotate-hint,.sr-only{display:none!important}
*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent}
html,body{height:auto!important;overflow:visible!important;background:var(--surface)!important}
body{display:block!important;margin:0!important}
.deck{display:block!important;position:static!important;max-width:none!important;width:auto!important;margin:0!important;padding:0!important}
.slide-frame{position:static!important;display:block!important;visibility:visible!important;padding:0!important;break-after:page}
.slide-frame:last-child{break-after:auto}
.slide-box{width:1280px!important;height:720px!important}
.slide{width:1280px!important;height:720px!important;transform:none!important;border:0!important;border-radius:0!important;box-shadow:none!important;user-select:text!important}
.build-pending{opacity:1!important}
:root:has(.slide-frame:target) .slide-frame:not(:target){display:none!important}
@page{size:1280px 720px;margin:0}
"""
# A preview inside the editor shows the slide alone at the canvas's own size; the editor scales the frame it sits in.
PREVIEW_CSS = (".deck-bar,.deck-nav,.notes{display:none!important}"
               ".js-deck .deck{--scale:1!important}.js-deck .slide-frame{padding:0!important}")


class ExportError(RuntimeError):
    def __init__(self, message: str, status: int = 500):
        super().__init__(message)
        self.status = status


def find_browser() -> str:
    """The browser to print with: DISTILL_BROWSER, then Edge and Chrome in their usual folders, then the PATH."""
    chosen = os.environ.get("DISTILL_BROWSER", "").strip().strip('"')
    if chosen:
        if Path(chosen).is_file():
            return chosen
        raise ExportError(f"DISTILL_BROWSER points to {chosen}, which is not a file. Fix it or remove it.", 424)
    folders = [os.environ.get(name) for name in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")]
    known = [Path(folder) / suffix for suffix in (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe")
             for folder in folders if folder]
    for path in known:
        if path.is_file():
            return str(path)
    for name in ("msedge", "chrome", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    raise ExportError(NO_BROWSER, 424)


def export_page(page: str, theme: str = "light") -> str:
    """The deck page prepared for the browser; paper and projectors are light, so that is the look drawn unless asked."""
    theme = theme if theme in ("light", "dark") else "light"
    # The deck's own theme script sets its saved (or dark) theme again when the page has loaded, so this one runs after it.
    pick = f'document.documentElement.dataset.theme="{theme}";document.documentElement.style.colorScheme="{theme}"'
    head = f'<style id="export">{EXPORT_CSS}</style><script>{pick};document.addEventListener("DOMContentLoaded",()=>{{{pick}}})</script>'
    return page.replace("</head>", head + "</head>", 1)


def slide_count(page: str) -> int:
    return len(re.findall(r'class="slide-frame"', page))


def only_slide(page: str, at: str) -> str:
    """The deck page with only the slide at "P.S" in view, for a preview in the editor."""
    found = re.search(rf'id="slide-(\d+)"[^>]*data-slide="{re.escape(at)}"', page)
    if not found:
        raise ExportError("This slide is not in the deck.", 404)
    number = int(found[1])
    hide = f'<style id="only">{PREVIEW_CSS}.slide-frame:not([data-slide="{at}"]){{display:none!important}}</style>'
    jump = f"<script>location.hash='#slide-{number}'</script>"
    return page.replace("</head>", hide + "</head>", 1).replace("</body>", jump + "</body>", 1)


def command(browser: str, profile: Path, *flags: str) -> list[str]:
    """One headless launch in its own empty profile, so no other window of the browser is touched or waited for."""
    return [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
            "--disable-extensions", "--disable-sync", "--mute-audio", f"--user-data-dir={profile}", f"--virtual-time-budget={VIRTUAL_TIME}", *flags]


def pdf_command(browser: str, profile: Path, page: Path, output: Path, slide: int | None = None) -> list[str]:
    """Print the deck page, or one slide of it, to a PDF of 1280x720 px pages without the browser's headers and footers."""
    return command(browser, profile, f"--print-to-pdf={output}", "--no-pdf-header-footer", address(page, slide))


def png_command(browser: str, profile: Path, page: Path, output: Path, slide: int, scale: int) -> list[str]:
    """Screenshot one slide in a window of the canvas's size; scale 2 gives 2560x1440 pixels."""
    return command(browser, profile, f"--screenshot={output}", f"--window-size={WIDTH},{HEIGHT}", f"--force-device-scale-factor={scale}", address(page, slide))


def address(page: Path, slide: int | None) -> str:
    return page.resolve().as_uri() + (f"#slide-{slide}" if slide else "")


def launch(arguments: list[str], output: Path) -> bytes:
    """Run one launch and read what it wrote. A launch that hangs is ended with everything it started."""
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        process = subprocess.Popen(arguments, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, creationflags=flags)
    except OSError as error:
        raise ExportError(f"The browser could not start: {error}", 502) from error
    try:
        _, errors = process.communicate(timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True, creationflags=flags)
        else:
            process.kill()
        process.communicate()
        raise ExportError("The browser took too long to draw the slides. Close other windows and try again.", 504) from None
    if not output.is_file() or output.stat().st_size == 0:
        detail = errors.decode("utf-8", "replace").strip().splitlines()[-1:] if errors else []
        raise ExportError("The browser did not draw the slides" + (f": {detail[0][:200]}" if detail else ".") , 502)
    return output.read_bytes()


def work_folder() -> Path:
    return Path(tempfile.mkdtemp(prefix="distill-export-"))


def render_pdf(page: str, slide: int | None = None, theme: str = "light", browser: str | None = None) -> bytes:
    browser = browser or find_browser()
    folder = work_folder()
    try:
        file = folder / "deck.html"
        file.write_text(export_page(page, theme), encoding="utf-8")
        output = folder / "slides.pdf"
        return launch(pdf_command(browser, folder / "profile", file, output, slide), output)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def render_png(page: str, slides: list[int], scale: int = 1, theme: str = "light", browser: str | None = None) -> list[tuple[int, bytes]]:
    """One picture per slide, three launches at a time."""
    browser = browser or find_browser()
    folder = work_folder()
    try:
        file = folder / "deck.html"
        file.write_text(export_page(page, theme), encoding="utf-8")

        def one(number: int) -> tuple[int, bytes]:
            output = folder / f"slide-{number}.png"
            return number, launch(png_command(browser, folder / f"profile-{number}", file, output, number, scale), output)

        with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
            return list(pool.map(one, slides))
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def pictures_zip(pictures: list[tuple[int, bytes]], name: str) -> bytes:
    """Several pictures in one file, numbered so they sort in deck order."""
    width = max(2, len(str(max(number for number, _ in pictures))))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:  # PNG is compressed already
        for number, data in pictures:
            archive.writestr(f"{name}-{number:0{width}d}.png", data)
    return buffer.getvalue()
