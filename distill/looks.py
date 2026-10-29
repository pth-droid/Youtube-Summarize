"""Deck looks. Their colours and type live in reader_assets/slide-looks.css, copied from the slide-design skill;
this module names them for people, reads each look's tokens for the app's look picker and look editor, and applies
the changes a person saved to a look (Settings → Slide looks) to every deck shown in that look."""

from __future__ import annotations

from functools import cache
from pathlib import Path
import re

LOOKS_CSS = Path(__file__).parent / "reader_assets" / "slide-looks.css"

# Name and what each look suits, in the order the app offers them. Forest matches the app and stays the default.
SLIDE_LOOKS = {
    "forest": ("Forest green", "Teaching and explainers"),
    "maroon": ("Maroon and beige", "History, humanities, ceremonies"),
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
DISPLAY_FONTS = {"sitka": ("Sitka serif", "forest"), "book": ("Book serif · Iowan, Palatino", "editorial"),
                 "aptos": ("Aptos", "navy"), "segoe": ("Segoe UI Variable", "contrast"),
                 "din": ("Bahnschrift · DIN", "slate"), "avenir": ("Avenir Next · Candara", "workshop")}
BODY_FONTS = {"system": ("System sans", "forest"), "aptos": ("Aptos", "navy"), "segoe": ("Segoe UI Variable", "contrast"),
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
    """A saved deck as it is shown now: in its own look, or in `look` for a preview, with that look's saved changes.
    The changes are added when a deck is shown, so changing a look restyles the decks already made in it."""
    found = DECK_LOOK.search(page)
    if not found:
        return page
    if look and look != found[2]:
        page = page[:found.start(2)] + look + page[found.end(2):]
    css = look_css(look or found[2], custom.get(look or found[2], {}))
    return page.replace("</head>", f'<style id="custom-look">{css}</style></head>', 1) if css else page


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
