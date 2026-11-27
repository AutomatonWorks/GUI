from __future__ import annotations

from dataclasses import dataclass

# Named color schemes for the GUI Theme, ported from guis/Palettes.ahk2.
# Each palette carries the same color roles + a `dark` flag. Colors are stored
# as 0xRRGGBB ints (as in the AHK source); convert to "#RRGGBB" with HexOf().
# STRUCTURE defines how palettes group in the Theme menu and in what order.


@dataclass(frozen=True)
class Palette:
    name: str
    dark: bool
    bg: int
    surface: int
    surface2: int
    hover: int
    border: int
    sep: int
    text: int
    subtle: int
    accent: int
    accentHi: int
    primaryFg: int


# ---- VS Code "Light Modern" ----
ModernLight = Palette(
    name="ModernLight",
    dark=False,
    bg=0xFFFFFF,
    surface=0xFFFFFF,
    surface2=0xE5E5E5,
    hover=0xCCCCCC,
    border=0xCECECE,
    sep=0xE5E5E5,
    text=0x3B3B3B,
    subtle=0x767676,
    accent=0x005FB8,
    accentHi=0x0258A8,
    primaryFg=0xFFFFFF,
)

# ---- VS Code "Dark Modern" ----
ModernDark = Palette(
    name="ModernDark",
    dark=True,
    bg=0x1F1F1F,
    surface=0x313131,
    surface2=0x313131,
    hover=0x3C3C3C,
    border=0x2B2B2B,
    sep=0x2B2B2B,
    text=0xCCCCCC,
    subtle=0x9D9D9D,
    accent=0x0078D4,
    accentHi=0x026EC1,
    primaryFg=0xFFFFFF,
)

# ---- Windows 11 (Fluent / WinUI) Light ----
Win11Light = Palette(
    name="Win11Light",
    dark=False,
    bg=0xF3F3F3,
    surface=0xFFFFFF,
    surface2=0xFBFBFB,
    hover=0xEDEDED,
    border=0xE5E5E5,
    sep=0xE5E5E5,
    text=0x1A1A1A,
    subtle=0x5D5D5D,
    accent=0x005FB7,
    accentHi=0x0258A8,
    primaryFg=0xFFFFFF,
)

# ---- Windows 11 (Fluent / WinUI) Dark ----
Win11Dark = Palette(
    name="Win11Dark",
    dark=True,
    bg=0x202020,
    surface=0x2D2D2D,
    surface2=0x2D2D2D,
    hover=0x383838,
    border=0x393939,
    sep=0x2D2D2D,
    text=0xFFFFFF,
    subtle=0xC8C8C8,
    accent=0x4CC2FF,  # SystemAccentColorLight2 - bright accent button
    accentHi=0x66CCFF,
    primaryFg=0x000000,  # dark text on the light-blue button
)

DEFAULT = "Win11Light"

# Theme menu layout: groups (submenus) in order; "" = no submenu.
STRUCTURE: list[tuple[str, list[tuple[str, str]]]] = [
    ("Modern", [("ModernLight", "Light"), ("ModernDark", "Dark")]),
    ("Windows 11", [("Win11Light", "Light"), ("Win11Dark", "Dark")]),
]

_BY_ID: dict[str, Palette] = {
    p.name.lower(): p
    for p in (ModernLight, ModernDark, Win11Light, Win11Dark)
}


def Has(paletteId: str) -> bool:
    """Is `paletteId` one of the defined themes? (case-insensitive)"""
    return paletteId.lower() in _BY_ID


def Get(paletteId: str) -> Palette:
    """Resolve a palette by id (case-insensitive). Raises KeyError if unknown."""
    return _BY_ID[paletteId.lower()]


def AllIds() -> list[str]:
    """Palette ids in STRUCTURE (menu) order."""
    return [pid for _group, items in STRUCTURE for pid, _label in items]


def HexOf(rgb: int) -> str:
    """0xRRGGBB -> '#RRGGBB' for QSS / Qt color strings."""
    return f"#{rgb & 0xFFFFFF:06X}"


def Mix(a: int, b: int, t: float) -> int:
    """Linear blend from `a` toward `b`; t 0.0 = a, 1.0 = b. 0xRRGGBB."""
    ar, ag, ab = (a >> 16) & 0xFF, (a >> 8) & 0xFF, a & 0xFF
    bR, bg, bB = (b >> 16) & 0xFF, (b >> 8) & 0xFF, b & 0xFF
    r = round(ar + (bR - ar) * t)
    g = round(ag + (bg - ag) * t)
    bl = round(ab + (bB - ab) * t)
    return (r << 16) | (g << 8) | bl


def Darken(rgb: int, factor: float) -> int:
    """Scale each channel toward black; factor 1.0 = unchanged, 0.0 = black."""
    return Mix(rgb, 0x000000, 1.0 - factor)
