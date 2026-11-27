from __future__ import annotations

import os
import shutil
import tempfile

from automaton_gui import BackupArchive, Inischema

# The setup wizard edits copies of the conf and the accounts file in a folder of its own, so the
# real files change only once, at Finish (FirstRun in commons copies the staged ones over them).
STAGED_KINDS = ("conf", "accounts")
FOLDER_PREFIX = "automaton-setup-"


class Staging:
    def __init__(self, files: dict[str, str], app: str, iniFiles: dict) -> None:
        """files: kind -> the real path, for every kind in STAGED_KINDS."""
        self.folder = tempfile.mkdtemp(prefix=FOLDER_PREFIX)
        self.app = app
        self.iniFiles = iniFiles
        # the backup the user imported, restored whole at Finish; "" when none
        self.backup = ""
        self.paths = {kind: os.path.join(self.folder, os.path.basename(files[kind])) for kind in STAGED_KINDS}
        for kind, real in files.items():
            if os.path.isfile(real):
                shutil.copyfile(real, self.paths[kind])
            self._BringUpToDate(kind)

    @property
    def conf(self) -> str:
        return self.paths["conf"]

    @property
    def accounts(self) -> str:
        return self.paths["accounts"]

    def Import(self, zipPath: str) -> dict:
        """Loads a backup's conf and accounts into the copies; BackupError when this app cannot restore it."""
        manifest = BackupArchive.Validate(zipPath, self.app, self.iniFiles)
        contents = BackupArchive.ReadFiles(zipPath, manifest)
        for kind in STAGED_KINDS:
            if kind in contents:
                with open(self.paths[kind], "wb") as staged:
                    staged.write(contents[kind])
                self._BringUpToDate(kind)
        self.backup = zipPath
        return manifest

    def Discard(self) -> None:
        shutil.rmtree(self.folder, ignore_errors=True)

    # a missing file is created with its defaults and an older one migrated, as at startup
    def _BringUpToDate(self, kind: str) -> None:
        Inischema.Update(self.iniFiles[kind], self.paths[kind], self.app)
