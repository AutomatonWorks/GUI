"""Keeps a game's INI files in step with its schema, app/utils/IniGenerator.py.

AHK runs `python -m automaton_gui.inischema --schema <IniGenerator.py> --app <name>
--file conf=<path> ...` on every start, before it reads any of those files.
For each file:
  missing           written from the schema
  version older     a .bak is kept, the migrations run, then the file is rewritten
  schema changed    rewritten, so new keys, defaults and comments need no version bump
A rewrite follows the schema's order and comments and keeps every value already
set. Keys and sections the schema doesn't know are kept too, at the end of their
section or of the file: removing one takes a migration. Comments above a schema
key always come from the schema; other comments the user wrote stay with the key
they precede, or at the end of the section when none follows.

The schema module exposes FILES = {"conf": IniFile(...), ...}, keyed like --file.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import sys
import textwrap
import traceback
from pathlib import Path
from types import ModuleType
from typing import Callable

from automaton_gui import Secrets

META = "Meta"
GENERATED_NOTES = (
    "# Not part of the current template, kept as it was",
    "# Written by the automaton to keep this file up to date, do not edit",
)
SECTION_END = None


class Key:
    """secret: stored encrypted (automaton_gui.Secrets); a plain value found in the file is encrypted on the next start."""

    def __init__(self, name: str, default: object = "", comment: str = "", secret: bool = False) -> None:
        self.name = name
        self.default = default
        self.comment = comment
        self.secret = secret


class Section:
    """items are Keys, or strings: a comment block starting a new group of keys.
    free: any keys, copied as they are (a user-defined [Dev]).
    repeated: name is a prefix, every [<name><number>] section follows this
    layout and missing keys are not filled in (an [AccountN] with no mail key
    is not an account)."""

    def __init__(self, name: str, items: list | None = None, free: bool = False, repeated: bool = False) -> None:
        self.name = name
        self.items = list(items or [])
        self.free = free
        self.repeated = repeated

    @property
    def keys(self) -> list[Key]:
        return [item for item in self.items if isinstance(item, Key)]


class IniFile:
    """version goes up only when a change needs migrations: {version: [steps]},
    each run on files older than that version."""

    def __init__(self, sections: list[Section], version: int = 1, header: str = "",
                 migrations: dict[int, list[Callable]] | None = None) -> None:
        self.sections = sections
        self.version = version
        self.header = header
        self.migrations = migrations or {}

    def Default(self, section: str, key: str) -> object:
        for sec in self.sections:
            if sec.name.casefold() == section.casefold():
                for k in sec.keys:
                    if k.name.casefold() == key.casefold():
                        return k.default
        raise KeyError(f"[{section}] {key} is not in the schema")

    def Checksum(self) -> str:
        layout = [self.version, self.header]
        for sec in self.sections:
            layout.append((sec.name, sec.free, sec.repeated, [
                _KeyLayout(item) if isinstance(item, Key) else item
                for item in sec.items]))
        return hashlib.sha1(repr(layout).encode("utf-8")).hexdigest()[:12]

    def IsSecret(self, section: str, key: str) -> bool:
        for sec in self.sections:
            if _SectionMatches(sec, section):
                return any(k.secret and (k.name.casefold() == key.casefold()) for k in sec.keys)
        return False


# a plain key keeps the tuple it always had, so marking a key secret only changes that file's checksum
def _KeyLayout(key: Key) -> tuple:
    layout = (key.name, _Value(key.default), key.comment)
    if key.secret:
        return layout + ("secret",)
    return layout


def _SectionMatches(sec: Section, name: str) -> bool:
    if not sec.repeated:
        return sec.name.casefold() == name.casefold()
    prefix = sec.name.casefold()
    return name.casefold().startswith(prefix) and name[len(prefix):].isdigit()


# ---- the file's contents -----------------------------------------------------


class IniData:
    """Sections and keys in file order, matched case-insensitively like the
    Windows INI API; the first of a duplicated key wins, as it does there."""

    def __init__(self) -> None:
        self._sections: dict[str, list] = {}   # casefold -> [name, {casefold key: [key, value]}]
        self._notes: dict[tuple[str, str | None], list[str]] = {}   # (section, key or SECTION_END) -> comment lines

    def Notes(self, section: str, key: str | None) -> list[str]:
        return self._notes.get((section.casefold(), None if key is None else key.casefold()), [])

    def SectionNames(self) -> list[str]:
        return [name for name, _ in self._sections.values()]

    def Matching(self, pattern: str) -> list[str]:
        """The section itself, or for "Prefix*" every [Prefix<number>] in numeric order."""
        if not pattern.endswith("*"):
            return [pattern] if pattern.casefold() in self._sections else []
        prefix = pattern[:-1].casefold()
        found = [name for name, _ in self._sections.values()
                 if name.casefold().startswith(prefix) and name[len(prefix):].isdigit()]
        return sorted(found, key=lambda name: int(name[len(prefix):]))

    def HasSection(self, section: str) -> bool:
        return section.casefold() in self._sections

    def Items(self, section: str) -> list[tuple[str, str]]:
        entry = self._sections.get(section.casefold())
        return [] if entry is None else [(k, v) for k, v in entry[1].values()]

    def Get(self, section: str, key: str) -> str | None:
        entry = self._sections.get(section.casefold())
        if entry is None:
            return None
        pair = entry[1].get(key.casefold())
        return None if pair is None else pair[1]

    def Set(self, section: str, key: str, value: str) -> None:
        entry = self._sections.setdefault(section.casefold(), [section, {}])
        pair = entry[1].get(key.casefold())
        if pair is None:
            entry[1][key.casefold()] = [key, value]
        else:
            pair[1] = value

    def AddIfMissing(self, section: str, key: str, value: str) -> None:
        if self.Get(section, key) is None:
            self.Set(section, key, value)

    def Pop(self, section: str, key: str) -> str | None:
        entry = self._sections.get(section.casefold())
        if entry is None:
            return None
        pair = entry[1].pop(key.casefold(), None)
        return None if pair is None else pair[1]

    def PopSection(self, section: str) -> list[tuple[str, str]]:
        entry = self._sections.pop(section.casefold(), None)
        return [] if entry is None else [(k, v) for k, v in entry[1].values()]

    def RenameSection(self, old: str, new: str) -> None:
        for key, value in self.PopSection(old):
            self.AddIfMissing(new, key, value)


def Parse(text: str) -> IniData:
    data = IniData()
    current = None
    pending: list[str] = []

    def KeepPending(key: str | None) -> None:
        notes = [line for line in pending if line not in GENERATED_NOTES]
        while notes and not notes[0]:
            notes.pop(0)
        while notes and not notes[-1]:
            notes.pop()
        if current is not None and notes:
            data._notes.setdefault((current.casefold(), None if key is None else key.casefold()), notes)
        pending.clear()

    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        stripped = line.strip()
        if not stripped or stripped[0] in "#;":
            pending.append(stripped)
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            KeepPending(SECTION_END)
            current = stripped[1:-1].strip()
            data._sections.setdefault(current.casefold(), [current, {}])
            continue
        if current is None or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        KeepPending(key.strip())
        data.AddIfMissing(current, key.strip(), value.strip())
    KeepPending(SECTION_END)
    return data


# ---- migration steps ---------------------------------------------------------
# A section may be "Prefix*" for every [Prefix<number>]. Any callable taking the
# IniData works as a step too.


class RenameKey:
    def __init__(self, section: str, old: str, new: str) -> None:
        self.section, self.old, self.new = section, old, new

    def __call__(self, data: IniData) -> None:
        for section in data.Matching(self.section):
            value = data.Pop(section, self.old)
            if value is not None:
                data.AddIfMissing(section, self.new, value)


class MoveKey:
    def __init__(self, section: str, key: str, toSection: str, toKey: str | None = None) -> None:
        self.section, self.key, self.toSection, self.toKey = section, key, toSection, toKey

    def __call__(self, data: IniData) -> None:
        value = data.Pop(self.section, self.key)
        if value is not None:
            data.AddIfMissing(self.toSection, self.toKey or self.key, value)


class RenameSection:
    def __init__(self, old: str, new: str) -> None:
        self.old, self.new = old, new

    def __call__(self, data: IniData) -> None:
        data.RenameSection(self.old, self.new)


class MapValue:
    def __init__(self, section: str, key: str, mapping: dict[str, str]) -> None:
        self.section, self.key, self.mapping = section, key, mapping

    def __call__(self, data: IniData) -> None:
        for section in data.Matching(self.section):
            value = data.Get(section, self.key)
            if value in self.mapping:
                data.Set(section, self.key, self.mapping[value])


class SetKey:
    def __init__(self, section: str, key: str, value: object) -> None:
        self.section, self.key, self.value = section, key, value

    def __call__(self, data: IniData) -> None:
        data.Set(self.section, self.key, _Value(self.value))


class DeleteKey:
    def __init__(self, section: str, key: str) -> None:
        self.section, self.key = section, key

    def __call__(self, data: IniData) -> None:
        for section in data.Matching(self.section):
            data.Pop(section, self.key)


class DeleteSection:
    def __init__(self, section: str) -> None:
        self.section = section

    def __call__(self, data: IniData) -> None:
        for section in data.Matching(self.section):
            data.PopSection(section)


# ---- writing -----------------------------------------------------------------


def _Value(value: object) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def _CommentLines(text: str) -> list[str]:
    lines = textwrap.dedent(text).strip("\n").split("\n") if text.strip() else []
    return [line if line.startswith("#") else ("# " + line).rstrip() for line in lines]


def _SchemaComments(schema: IniFile, app: str) -> set[str]:
    lines = set(_CommentLines(schema.header.replace("{app}", app)))
    for sec in schema.sections:
        for item in sec.items:
            lines.update(_CommentLines(item if isinstance(item, str) else item.comment))
    return lines


def _UserNotes(data: IniData, generated: set[str], section: str, key: str | None) -> list[str]:
    return [line for line in data.Notes(section, key) if line not in generated]


def _PairsWithNotes(data: IniData, generated: set[str], section: str,
                      pairs: list[tuple[str, str]]) -> list[str]:
    out = []
    for k, v in pairs:
        out.extend(_UserNotes(data, generated, section, k))
        out.append(f"{k}={v}")
    return out


def _RenderSection(sec: Section, name: str, data: IniData, generated: set[str]) -> list[str]:
    out = [f"[{name}]"]
    known = set()
    schemaCommentAbove = False
    items = [] if sec.free else sec.items
    for index, item in enumerate(items):
        if isinstance(item, str):
            if index > 0:
                out.append("")
            out.extend(_CommentLines(item))
            schemaCommentAbove = True
            continue
        known.add(item.name.casefold())
        value = data.Get(name, item.name)
        if value is None and sec.repeated:
            continue
        schemaCommentAbove = schemaCommentAbove or bool(item.comment.strip())
        # Where the schema writes a comment above a key, the file's lines there
        # are an older copy of it: the schema's replaces them so an edited
        # comment does not pile up. Notes above uncommented keys are the user's.
        if not schemaCommentAbove:
            out.extend(_UserNotes(data, generated, name, item.name))
        out.extend(_CommentLines(item.comment))
        out.append(f"{item.name}={_Value(item.default) if value is None else value}")
        schemaCommentAbove = False
    unknown = [(k, v) for k, v in data.Items(name) if k.casefold() not in known]
    out.extend(_PairsWithNotes(data, generated, name, unknown))
    out.extend(_UserNotes(data, generated, name, SECTION_END))
    return out


def _RenderUnknownSections(data: IniData, handled: set[str], generated: set[str]) -> list[list[str]]:
    blocks = []
    for name in data.SectionNames():
        if name.casefold() not in handled:
            block = [f"[{name}]"]
            block.extend(_PairsWithNotes(data, generated, name, data.Items(name)))
            block.extend(_UserNotes(data, generated, name, SECTION_END))
            blocks.append(block)
    return blocks


def Render(schema: IniFile, data: IniData, app: str) -> str:
    generated = _SchemaComments(schema, app)
    handled = {META.casefold()}
    blocks = []
    for sec in schema.sections:
        names = data.Matching(sec.name + "*") if sec.repeated else [sec.name]
        for name in names:
            handled.add(name.casefold())
            if sec.free and not data.HasSection(name):
                continue
            blocks.append(_RenderSection(sec, name, data, generated))
    blocks.extend(_RenderUnknownSections(data, handled, generated))
    blocks.append([f"[{META}]", f"version={schema.version}", f"schema={schema.Checksum()}"])

    out = _CommentLines(schema.header.replace("{app}", app))
    if out:
        out.append("")
    for block in blocks:
        out.extend(block)
    return "\r\n".join(out) + "\r\n"


def _ProtectSecrets(schema: IniFile, text: str) -> str:
    """The text with every plain value of a secret key encrypted; the rest is left byte for byte."""
    lines = text.split("\n")
    section = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].strip()
            continue
        if (section is None) or ("=" not in stripped) or (stripped[0] in "#;"):
            continue
        key, _, value = stripped.partition("=")
        value = value.strip()
        if (value == "") or Secrets.IsProtected(value) or (not schema.IsSecret(section, key.strip())):
            continue
        ending = "\r" if line.endswith("\r") else ""
        lines[index] = f"{key.strip()}={Secrets.Protect(value)}{ending}"
    return "\n".join(lines)


def _Read(path: Path) -> str:
    # surrogateescape: values the AHK INI API wrote in the ANSI codepage survive untouched
    return path.read_bytes().decode("utf-8-sig", errors="surrogateescape")


def _Write(path: Path, text: str) -> None:
    # UTF-8, no BOM, CRLF: a BOM or LF-only file breaks section enumeration in the AHK INI API
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(text.encode("utf-8", errors="surrogateescape"))
    os.replace(tmp, path)


def Update(schema: IniFile, path: str | Path, app: str) -> str:
    """Brings one file up to date; returns what happened, "" when nothing did."""
    path = Path(path)
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        _Write(path, Render(schema, IniData(), app))
        return f"Created {path.name}"
    read = _Read(path)
    # the .bak below is written from this text too, so no plain secret is ever left on disk
    original = _ProtectSecrets(schema, read)
    data = Parse(original)
    try:
        version = int(data.Get(META, "version") or 0)
    except ValueError:
        version = 0
    upToDate = (version == schema.version) and (data.Get(META, "schema") == schema.Checksum())
    if upToDate and (original == read):
        return ""
    if version > schema.version:
        return f"{path.name} is from a newer version of the app (file version {version}), left as it is"
    backup = path.with_name(path.name + ".bak")
    _Write(backup, original)
    for stepVersion in range(version + 1, schema.version + 1):
        for step in schema.migrations.get(stepVersion, []):
            step(data)
    _Write(path, Render(schema, data, app))
    if version < schema.version:
        return f"Updated {path.name} from version {version} to {schema.version}, the old one is {backup.name}"
    return f"Updated {path.name} to the current template, the old one is {backup.name}"


# ---- the game's schema -------------------------------------------------------


def FindSchema(near: str | Path) -> Path:
    """IniGenerator.py beside `near` (compiled builds install them together),
    or in the app's utils folder (`near` being app/gui/game_conf.py)."""
    near = Path(near).resolve()
    for candidate in (near.parent / "IniGenerator.py", near.parent.parent / "utils" / "IniGenerator.py"):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"IniGenerator.py not found next to {near}")


def LoadSchema(path: str | Path) -> ModuleType:
    path = Path(path)
    spec = importlib.util.spec_from_file_location("IniGenerator", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def Main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--schema", required=True)
    parser.add_argument("--app", required=True)
    parser.add_argument("--file", action="append", default=[], metavar="NAME=PATH")
    args = parser.parse_args(argv)
    try:
        files = LoadSchema(args.schema).FILES
        for spec in args.file:
            name, _, path = spec.partition("=")
            if name not in files:
                raise KeyError(f"{name} is not one of the schema's files: {', '.join(files)}")
            message = Update(files[name], path, args.app)
            if message:
                print(message)
    except Exception:
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(Main())
