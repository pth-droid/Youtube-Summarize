"""Deck looks. Their colours and type live in reader_assets/slide-looks.css, copied from the slide-design skill;
this module names them for people and reads each look's light colours for the app's look picker."""

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


def look_tokens(css: str) -> dict[str, dict[str, str]]:
    """Each look's light tokens, from its :root[data-look=NAME] block (dark blocks carry a second attribute)."""
    return {match[1]: dict(re.findall(r"--([\w-]+):([^;]+)", match[2]))
            for match in re.finditer(r":root\[data-look=([\w-]+)\]\{([^}]*)\}", css)}


@cache
def look_swatches() -> list[dict]:
    tokens = look_tokens(LOOKS_CSS.read_text(encoding="utf-8"))
    return [{"id": look, "name": name, "hint": hint, "tokens": {key: tokens[look][key].strip() for key in SWATCH_TOKENS}}
            for look, (name, hint) in SLIDE_LOOKS.items()]
