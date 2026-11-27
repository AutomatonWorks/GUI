"""What a backup zip holds and whether this app can restore it. Shared by the Data menu's restore (commons)
and the setup wizard's import, which reads a zip before anything is written."""

from __future__ import annotations

import json
import zipfile

from automaton_gui import Inischema

MANIFEST = "backup.json"
MANIFEST_SCHEMA = "automaton-backup"
MANIFEST_VERSION = 1
# every file a backup can hold, by kind
DATA_KINDS = ("conf", "accounts", "sav", "locks")
# the files Inischema keeps; a zip with a newer file version than this app knows is refused
INI_KINDS = ("conf", "accounts", "sav")


class BackupError(Exception):
    """Why a zip cannot be restored: textId is its Locale id, detail fills its {1}."""

    def __init__(self, textId: str, detail: str = "") -> None:
        super().__init__(f"{textId} {detail}".strip())
        self.textId = textId
        self.detail = detail


def Validate(path: str, app: str, iniFiles: dict) -> dict:
    """The zip's manifest when `app` can restore it (iniFiles: the app's Inischema files by kind)."""
    if not zipfile.is_zipfile(path):
        raise BackupError("data.restore.not_a_backup")
    try:
        with zipfile.ZipFile(path) as archive:
            manifest = _Manifest(archive, app)
            for kind, name in manifest["files"].items():
                if kind in INI_KINDS:
                    _CheckIniVersion(archive.read(name), iniFiles[kind])
    except zipfile.BadZipFile:
        raise BackupError("data.restore.not_a_backup") from None
    return manifest


def ReadFiles(path: str, manifest: dict) -> dict[str, bytes]:
    """kind -> content of every file the zip holds."""
    with zipfile.ZipFile(path) as archive:
        return {kind: archive.read(name) for kind, name in manifest["files"].items()}


def _Manifest(archive: zipfile.ZipFile, app: str) -> dict:
    try:
        manifest = json.loads(archive.read(MANIFEST).decode("utf-8"))
    except (KeyError, ValueError):
        raise BackupError("data.restore.not_a_backup") from None
    if (not isinstance(manifest, dict)) or (manifest.get("schema") != MANIFEST_SCHEMA):
        raise BackupError("data.restore.not_a_backup")
    if manifest.get("version", 0) > MANIFEST_VERSION:
        raise BackupError("data.restore.newer_app")
    if manifest.get("app") != app:
        raise BackupError("data.restore.other_app", str(manifest.get("app", "")))
    files = manifest.get("files")
    names = set(archive.namelist())
    if (not isinstance(files, dict)) or any((kind not in DATA_KINDS) or (name not in names) for kind, name in files.items()):
        raise BackupError("data.restore.not_a_backup")
    return manifest


def _CheckIniVersion(content: bytes, schema: Inischema.IniFile) -> None:
    data = Inischema.Parse(content.decode("utf-8-sig", errors="surrogateescape"))
    try:
        version = int(data.Get(Inischema.META, "version") or 0)
    except ValueError:
        version = 0
    # an older file is fine: Inischema migrates it like any other
    if version > schema.version:
        raise BackupError("data.restore.newer_app")
