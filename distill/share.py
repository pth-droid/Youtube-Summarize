"""Slides shared to a phone: a phone copy of a lecture deck, opened over the owner's tailnet or downloaded as one file.

The phone copy is rendered from the deck's saved records when the owner shares it; no AI request is made. Tailscale
serve proxies one path of this computer's tailnet name to this app's /share routes, so the rest of the app stays local.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from .looks import SLIDE_THEMES, with_custom_look
from .models import FigurePlan, KnowledgeModel, LecturePlan, Transcript
from .renderer import render_lecture, write_page

PHONE_PAGE = "lecture-phone.html"
# The tailnet path that reaches /share here. The computer's root and other paths may belong to other services.
TAILNET_PATH = "/distill/share"
SHARE_ID = re.compile(r"[0-9a-f]{32}")


def phone_page(store, generation: dict) -> Path:
    return store.managed_path(generation["page_path"]).parent / PHONE_PAGE


def deck_look(generation: dict, deck: Path) -> str:
    """The look the deck was made in. Decks made before looks were recorded carry it on their <html> tag."""
    look = generation.get("metadata", {}).get("slide_theme")
    if look not in SLIDE_THEMES and deck.is_file():
        found = re.search(r'data-(?:look|deck-theme)="([\w-]+)"', deck.read_text(encoding="utf-8")[:4000])
        look = found and found.group(1)
    return look if look in SLIDE_THEMES else "forest"


def render_phone(store, generation: dict) -> Path:
    """Write the phone copy beside the deck, from the records the deck was rendered from."""
    deck = store.managed_path(generation["page_path"])
    folder = deck.parent
    source = Transcript.model_validate_json((folder / "source.json").read_text(encoding="utf-8"))
    knowledge = KnowledgeModel.model_validate_json((folder / "knowledge.json").read_text(encoding="utf-8"))
    saved = json.loads((folder / "lecture.json").read_text(encoding="utf-8"))
    saved.pop("questions", None)  # decks saved while they still ended in a quiz
    figures = folder / "figures.json"
    plan = FigurePlan.model_validate_json(figures.read_text(encoding="utf-8")) if figures.is_file() else None
    phone = render_lecture(source, knowledge, LecturePlan.model_validate(saved), folder / PHONE_PAGE, plan,
                           deck_look(generation, deck), phone=True)
    # The phone copy is a file served as it is, so the look's saved changes go into it now.
    return write_page(phone, with_custom_look(phone.read_text(encoding="utf-8"), store.custom_looks()))


def qr_image(url: str) -> str:
    """An SVG QR code as a data URL, for a phone camera to open the link."""
    import segno
    return segno.make(url, error="m").svg_data_uri(border=2, dark="#000", light="#fff")


def tailscale_command() -> str | None:
    found = shutil.which("tailscale")
    if found:
        return found
    installed = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Tailscale" / "tailscale.exe"
    return str(installed) if installed.is_file() else None


def tailscale_link(port: int) -> dict:
    """This computer's tailnet address for /share, when Tailscale serve proxies it to this app's port."""
    target = f"http://127.0.0.1:{port}/share"
    result = {"installed": False, "connected": False, "url": None,
              "command": f"tailscale serve --bg --set-path {TAILNET_PATH} {target}"}
    command = tailscale_command()
    if not command:
        return result
    result["installed"] = True

    def read(*args):
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        done = subprocess.run([command, *args, "--json"], capture_output=True, text=True, timeout=5, creationflags=flags)
        return json.loads(done.stdout) if done.returncode == 0 and done.stdout.strip() else {}

    try:
        status, serve = read("status"), read("serve", "status")
    except (OSError, subprocess.SubprocessError, ValueError):
        return result
    result["connected"] = status.get("BackendState") == "Running"
    for address, site in (serve.get("Web") or {}).items():
        host, _, listen = address.rpartition(":")
        for path, handler in (site.get("Handlers") or {}).items():
            if (handler.get("Proxy") or "").rstrip("/") == target:
                result["url"] = f"https://{host}{'' if listen == '443' else ':' + listen}{path.rstrip('/')}"
                return result
    return result
