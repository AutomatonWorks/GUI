"""The GUI's reads and writes of the ini files, on configparser.

Sections and keys are looked up ignoring case, like the Windows INI API, and keep their case when written.
"""

from __future__ import annotations

import configparser
from pathlib import Path


def _Load(path: str | Path) -> configparser.ConfigParser:
    # Values may hold a literal %, and key case is kept as written.
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    if Path(path).is_file():
        parser.read(path, encoding="utf-8-sig")
    return parser


def _Save(parser: configparser.ConfigParser, path: str | Path) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        parser.write(handle, space_around_delimiters=False)


def _Find(names: list[str], wanted: str) -> str | None:
    folded = wanted.casefold()
    for name in names:
        if name.casefold() == folded:
            return name
    return None


def IniRead(path: str | Path, section: str, key: str, fallback: str = "") -> str:
    """The value of `key`; `fallback` when the file, section or key is missing."""
    parser = _Load(path)
    sectionName = _Find(parser.sections(), section)
    if sectionName is None:
        return fallback
    keyName = _Find(list(parser[sectionName]), key)
    if keyName is None:
        return fallback
    return parser[sectionName][keyName]


def IniApply(path: str | Path, updates: dict[tuple[str, str], object]) -> None:
    """Writes every {(section, key): value} of `updates` in one rewrite of the file."""
    parser = _Load(path)
    for (section, key), value in updates.items():
        sectionName = _Find(parser.sections(), section)
        if sectionName is None:
            parser.add_section(section)
            sectionName = section
        keyName = _Find(list(parser[sectionName]), key) or key
        parser[sectionName][keyName] = str(value)
    _Save(parser, path)


def DeleteSection(path: str | Path, section: str) -> None:
    if not Path(path).is_file():
        return
    parser = _Load(path)
    sectionName = _Find(parser.sections(), section)
    if sectionName is not None:
        parser.remove_section(sectionName)
        _Save(parser, path)
