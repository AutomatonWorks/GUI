from __future__ import annotations

from pathlib import Path

from automaton_gui.Game import ACCOUNT_NAME_KEY
from automaton_gui.screens.IniFile import IniRead

# Reads of the accounts file (Accounts.ini) shared by every screen that lists accounts.

ACCOUNT_PREFIX = "Account"
MAX_ACCOUNT_ID = 99  # AccountSettings.MAX


def ExistingAccounts(file: str | Path, maxAccount: int = MAX_ACCOUNT_ID) -> list[str]:
    """The [AccountN] sections that actually exist, detected by a present mail key
    (single-key reads, in id order)."""
    out: list[str] = []
    for i in range(maxAccount + 1):
        section = f"{ACCOUNT_PREFIX}{i}"
        if IniRead(file, section, "mail", "\b") != "\b":
            out.append(section)
    return out


def DisplayAccountName(file: str | Path, section: str) -> str:
    """AccountName if set, else the mail, else the bare section id - so an
    account never renders blank wherever it is picked from (the account settings
    header, the General settings dropdown, the launch window's account selector)."""
    name = IniRead(file, section, ACCOUNT_NAME_KEY, "")
    if name:
        return name
    mail = IniRead(file, section, "mail", "")
    return mail if mail else section
