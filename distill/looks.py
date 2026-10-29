"""Deck looks. Their colours and type live in reader_assets/slide-looks.css, copied from the slide-design skill;
this module names them for people, reads each look's tokens for the app's look picker and look editor, and applies
each look as designed today, with the changes a person saved to it (Settings → Slide looks), to every deck shown in it."""

from __future__ import annotations

import base64
from functools import cache
from pathlib import Path
import re

LOOKS_CSS = Path(__file__).parent / "reader_assets" / "slide-looks.css"
# Fonts a look may name that most computers and phones lack. A deck whose type names one carries it inside the file,
# subset to Latin and Vietnamese (web/fonts/README.md); the app serves the same file for its look pickers.
FONTS_DIR = Path(__file__).parent / "web" / "fonts"
EMBEDDED_FONTS = {"Bricolage Grotesque": "bricolage-grotesque.woff2"}

# Name and what each look suits, in the order the app offers them. Forest matches the app and stays the default.
SLIDE_LOOKS = {
    "forest": ("Forest green", "Teaching and explainers"),
    "maroon": ("Maroon and beige", "Lighthouse brand, hospitality and history"),
    "navy": ("Navy and ivory", "Business reviews and pitches"),
    "contrast": ("High contrast", "Bright rooms, weak projectors"),
    "editorial": ("Editorial", "Essays, books and culture"),
    "slate": ("Slate and petrol", "Engineering, data and code"),
    "workshop": ("Workshop violet", "Workshops and trainings"),
}
SLIDE_THEMES = tuple(SLIDE_LOOKS)
# What a swatch draws: the slide, its text, a filled statement panel and the five data series.
SWATCH_TOKENS = ("surface", "ink", "muted", "line", "accent", "tint", "feature", "on-feature",
                 "data-1", "data-2", "data-3", "data-4", "data-5", "display")
# The colours a person can change, in light and in dark: the token contract every look defines.
COLOR_TOKENS = ("surface", "paper", "ink", "muted", "line", "accent", "on-accent", "tint", "feature", "on-feature",
                "data-1", "data-2", "data-3", "data-4", "data-5", "warning", "warning-bg", "inference", "focus")
# Type a look can switch to: the stacks the seven looks were designed with, read from the look named here.
# Installed fonts only, so nothing downloads; each stack covers Vietnamese on Windows.
DISPLAY_FONTS = {"bricolage": ("Bricolage Grotesque", "maroon"), "sitka": ("Sitka serif", "forest"),
                 "book": ("Book serif · Iowan, Palatino", "editorial"),
                 "aptos": ("Aptos", "navy"), "segoe": ("Segoe UI Variable", "contrast"),
                 "din": ("Bahnschrift · DIN", "slate"), "avenir": ("Avenir Next · Candara", "workshop")}
BODY_FONTS = {"bricolage": ("Bricolage Grotesque", "maroon"), "system": ("System sans", "forest"), "aptos": ("Aptos", "navy"), "segoe": ("Segoe UI Variable", "contrast"),
              "humanist": ("Humanist sans · Seravek, Gill Sans", "editorial"), "avenir": ("Avenir Next", "workshop")}
DECK_LOOK = re.compile(r'(<html\b[^>]*\bdata-look=")([\w-]+)(")')


def look_tokens(css: str, dark: bool = False) -> dict[str, dict[str, str]]:
    """Each look's tokens, from its :root[data-look=NAME] block, or with dark=True from its [data-theme=dark] block."""
    selector = r":root\[data-look=([\w-]+)\]" + (r"\[data-theme=dark\]" if dark else "") + r"\{([^}]*)\}"
    return {match[1]: {key: value.strip() for key, value in re.findall(r"--([\w-]+):([^;]+)", match[2])}
            for match in re.finditer(selector, css)}


def full_hex(colour: str) -> str:
    """#abc as #aabbcc, lower case, as a colour input reports it."""
    colour = colour.lower()
    return "#" + "".join(c * 2 for c in colour[1:]) if len(colour) == 4 else colour


@cache
def designed_looks() -> dict[str, dict]:
    """Each look as designed: its light and dark colours and its display and body type."""
    css = LOOKS_CSS.read_text(encoding="utf-8")
    light, dark = look_tokens(css), look_tokens(css, dark=True)
    return {look: {"light": {key: full_hex(light[look][key]) for key in COLOR_TOKENS},
                   "dark": {key: full_hex(dark[look][key]) for key in COLOR_TOKENS},
                   "display": light[look]["display"], "sans": light[look]["sans"]} for look in SLIDE_LOOKS}


@cache
def look_blocks() -> dict[str, str]:
    """Each look's own CSS as designed: its light block and its screen-only dark block."""
    css = LOOKS_CSS.read_text(encoding="utf-8")
    return {look: re.search(rf":root\[data-look={look}\]\{{[^}}]*\}}", css)[0]
            + re.search(rf"@media screen\{{:root\[data-look={look}\]\[data-theme=dark\]\{{[^}}]*\}}\}}", css)[0]
            for look in SLIDE_LOOKS}


@cache
def font_face(family: str) -> str:
    data = base64.b64encode((FONTS_DIR / EMBEDDED_FONTS[family]).read_bytes()).decode("ascii")
    return (f'@font-face{{font-family:"{family}";src:url(data:font/woff2;base64,{data}) format("woff2");'
            "font-weight:200 800;font-style:normal;font-display:block}")


def font_faces(*stacks: str, page: str = "") -> str:
    """@font-face rules for the embedded fonts these type stacks name, unless the page carries them already."""
    return "".join(font_face(family) for family in EMBEDDED_FONTS
                   if any(f'"{family}"' in stack for stack in stacks) and f'font-family:"{family}";src:' not in page)


def font_stack(kind: str, font: str) -> str:
    return designed_looks()[(DISPLAY_FONTS if kind == "display" else BODY_FONTS)[font][1]][kind]


def font_choices() -> dict[str, list[dict]]:
    return {kind: [{"id": font, "name": name, "stack": font_stack(kind, font)} for font, (name, _) in table.items()]
            for kind, table in (("display", DISPLAY_FONTS), ("sans", BODY_FONTS))}


def look_changes(look: str, value: dict) -> dict:
    """What a person changed in a look, kept only where it differs from the look as designed, so a look the
    slide-design skill later refines still updates every token the person left alone."""
    designed = designed_looks()[look]
    changes = {}
    for mode in ("light", "dark"):
        colours = {key: colour.lower() for key, colour in (value.get(mode) or {}).items() if colour.lower() != designed[mode][key]}
        if colours:
            changes[mode] = colours
    for kind in ("display", "sans"):
        if value.get(kind) and font_stack(kind, value[kind]) != designed[kind]:
            changes[kind] = value[kind]
    return changes


def look_css(look: str, changes: dict) -> str:
    """CSS that lays a person's changes over the look as designed; dark colours stay on screen, like the look's own."""
    def declarations(tokens):
        return ";".join(f"--{key}:{value}" for key, value in tokens.items())
    light = dict(changes.get("light", {}))
    light.update({kind: font_stack(kind, changes[kind]) for kind in ("display", "sans") if kind in changes})
    css = f":root[data-look={look}]{{{declarations(light)}}}" if light else ""
    if changes.get("dark"):
        css += f"@media screen{{:root[data-look={look}][data-theme=dark]{{{declarations(changes['dark'])}}}}}"
    return css


def with_custom_look(page: str, custom: dict[str, dict], look: str | None = None) -> str:
    """A saved deck as it is shown now: in its own look, or in `look` for a preview, as the look is designed today, with
    the changes saved to it and any embedded font its type names. This is added when a deck is shown, so a change to a
    look, saved by a person or made to its design, restyles the decks already made in it."""
    found = DECK_LOOK.search(page)
    name = look or (found and found[2])
    if not found or name not in SLIDE_LOOKS:
        return page
    if name != found[2]:
        page = page[:found.start(2)] + name + page[found.end(2):]
    changes = custom.get(name, {})
    now = current_look(name, changes)
    # Last comes lecture.css's print rule, which these blocks would otherwise undo: print puts slides on their surface.
    css = (font_faces(now["display"], now["sans"], page=page) + look_blocks()[name] + look_css(name, changes)
           + "@media print{:root[data-look]{--paper:var(--surface)}}")
    return page.replace("</head>", f'<style id="look">{css}</style></head>', 1)


# Decks carry the scripts they were made with, so the look editor's preview adds its own: it takes the colours being
# tried from the workspace, as hex codes only. Type being tried arrives in the preview's address instead, so the deck
# loads with it and fits its text to it.
PREVIEW_SCRIPT = ("<script>addEventListener('message',event=>{const data=event.data;if(event.source!==parent||data?.type!=='distill-look')return;"
                  "for(const[key,value]of Object.entries(data.colours||{}))if(/^[a-z0-9-]{1,20}$/.test(key)&&/^#[0-9a-f]{6}$/i.test(value))"
                  "document.documentElement.style.setProperty('--'+key,value);});</script>")


def look_preview(page: str, custom: dict[str, dict], look: str, fonts: dict[str, str]) -> str:
    """A saved deck in `look` for the look editor: the look's saved changes with the type being tried ("" for the type
    as designed), and the script that takes the colours being tried."""
    changes = {key: value for key, value in custom.get(look, {}).items() if key not in fonts} | {kind: font for kind, font in fonts.items() if font}
    return with_custom_look(page, {look: changes}, look).replace("</body>", PREVIEW_SCRIPT + "</body>", 1)


def current_look(look: str, changes: dict) -> dict:
    """A look's colours and type with a person's changes applied."""
    designed = designed_looks()[look]
    return {"light": designed["light"] | changes.get("light", {}), "dark": designed["dark"] | changes.get("dark", {}),
            "display": font_stack("display", changes["display"]) if "display" in changes else designed["display"],
            "sans": font_stack("sans", changes["sans"]) if "sans" in changes else designed["sans"]}


def look_swatches(custom: dict[str, dict] | None = None) -> list[dict]:
    """The looks for the app's pickers, each with the light colours and title type it is shown in now."""
    custom = custom or {}
    swatches = []
    for look, (name, hint) in SLIDE_LOOKS.items():
        now = current_look(look, custom.get(look, {}))
        tokens = now["light"] | {"display": now["display"]}
        swatches.append({"id": look, "name": name, "hint": hint, "custom": bool(custom.get(look)),
                         "tokens": {key: tokens[key] for key in SWATCH_TOKENS}})
    return swatches


def look_details(custom: dict[str, dict]) -> dict:
    """Everything the look editor needs: each look as designed, the changes saved to it, and the type to choose from."""
    looks = []
    for look, (name, hint) in SLIDE_LOOKS.items():
        designed = designed_looks()[look]
        fonts = {kind: next((font for font in table if font_stack(kind, font) == designed[kind]), None)
                 for kind, table in (("display", DISPLAY_FONTS), ("sans", BODY_FONTS))}
        looks.append({"id": look, "name": name, "hint": hint, "designed": designed | {"fonts": fonts},
                      "changes": custom.get(look, {})})
    return {"looks": looks, "fonts": font_choices(), "tokens": list(COLOR_TOKENS)}
