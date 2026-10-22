"""
core/apps.py — Discovery of the applications installed on this computer.

The assistant must be able to open anything the user has installed, not only
the handful of applications that ship with a plugin. This module builds an
index of what is actually on the machine; the launcher and the plugins query
it, so "open WhatsApp" works even without a WhatsApp plugin.

Where the entries come from:

  Linux   the freedesktop ``.desktop`` files (system, user, Flatpak, Snap)
          plus every executable found on ``PATH``
  Windows the ``App Paths`` registry keys and the Start Menu shortcuts
  macOS   the ``.app`` bundles in ``/Applications`` and ``~/Applications``

The index is built once and cached; :meth:`AppIndex.refresh` rebuilds it.
"""

import difflib
import logging
import os
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.platform import IS_MACOS, IS_WINDOWS

logger = logging.getLogger("PRIVACY68.Apps")

#: Matches an environment variable assignment such as "LANG=en_US.UTF-8".
_ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


@dataclass
class AppEntry:
    """A single installed application."""

    name: str
    args: List[str] = field(default_factory=list)
    source: str = ""      # desktop | path | registry | startmenu | macos
    icon: str = ""
    keywords: str = ""

    @property
    def command(self) -> str:
        """The command as a human readable string (for logs)."""
        return " ".join(self.args)

    def launch(self) -> bool:
        """Starts the application detached from this process."""
        try:
            if self.source == "macos":
                cmd = ["open", "-a", self.args[0]]
            elif self.source == "startmenu" and IS_WINDOWS:
                # A .lnk shortcut is only understood by the shell.
                os.startfile(self.args[0])  # noqa: S606 - Windows shell object
                return True
            else:
                cmd = self.args
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=(not IS_WINDOWS),
                creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) if IS_WINDOWS else 0,
            )
            logger.info(f"Launched '{self.name}' via {self.command}")
            return True
        except Exception as e:
            logger.warning(f"Could not launch '{self.name}': {e}")
            return False


# ─────────────────────────────────────────────────────────────────────────────
# Parsing helpers
# ─────────────────────────────────────────────────────────────────────────────
def parse_exec(exec_line: str) -> List[str]:
    """
    Turns a freedesktop ``Exec=`` line into an argument list.

    ``%U``/``%F``/``%u``/``%f`` field codes are removed, and a leading
    ``env VAR=value`` wrapper is skipped, but every other argument is kept —
    Flatpak entries rely on ``flatpak run com.example.App``.
    """
    try:
        parts = shlex.split(exec_line)
    except ValueError:
        parts = exec_line.split()

    cleaned: List[str] = []
    for part in parts:
        if part.startswith("%"):
            continue
        if part in ("env", "nice", "ionice", "dbus-run-session", "sh", "bash"):
            continue
        if _ENV_ASSIGN_RE.match(part):
            # An environment variable assignment ("FOO=bar").
            continue
        # A field code glued to an argument ("--file=%F").
        if "%" in part:
            head = part.split("%")[0]
            if not head:
                continue
            part = head
        cleaned.append(part)
    return cleaned


def _read_desktop_file(path: str) -> Optional[AppEntry]:
    """Parses a freedesktop .desktop file into an AppEntry."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            content = handle.read()
    except OSError:
        return None

    if "NoDisplay=true" in content:
        return None

    fields: Dict[str, str] = {}
    for line in content.splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        fields.setdefault(key.strip(), value.strip())

    name = fields.get("Name") or fields.get("GenericName")
    args = parse_exec(fields.get("Exec", ""))
    if not name or not args:
        return None

    return AppEntry(
        name=name,
        args=args,
        source="desktop",
        icon=fields.get("Icon", ""),
        keywords=fields.get("Keywords", ""),
    )


def _desktop_directories() -> List[str]:
    """Returns the directories that hold .desktop entries on this system."""
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, ".local", "share", "applications"),
        "/usr/local/share/applications",
        "/usr/share/applications",
        "/var/lib/flatpak/exports/share/applications",
        os.path.join(home, ".local", "share", "flatpak", "exports", "share", "applications"),
        "/var/lib/snapd/desktop/applications",
    ]
    return [d for d in candidates if os.path.isdir(d)]


# ─────────────────────────────────────────────────────────────────────────────
# Scanners — one per operating system
# ─────────────────────────────────────────────────────────────────────────────
def _scan_linux(entries: Dict[str, AppEntry]) -> None:
    """Collects the .desktop entries and the PATH executables."""
    for folder in _desktop_directories():
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        for filename in names:
            if not filename.endswith(".desktop"):
                continue
            entry = _read_desktop_file(os.path.join(folder, filename))
            if entry:
                # The file name ("firefox.desktop") is a useful alias too.
                entries.setdefault(filename[: -len(".desktop")].lower(), entry)
                entries.setdefault(entry.name.lower(), entry)

    for folder in os.environ.get("PATH", "").split(os.pathsep):
        if not folder or not os.path.isdir(folder):
            continue
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        for filename in names:
            if filename.startswith(".") or "-" in filename:
                continue
            full = os.path.join(folder, filename)
            if os.path.isdir(full) or not os.access(full, os.X_OK):
                continue
            entries.setdefault(filename.lower(), AppEntry(filename, [full], "path"))


def _scan_windows(entries: Dict[str, AppEntry]) -> None:
    """Collects the App Paths registry entries and the Start Menu shortcuts."""
    try:
        import winreg
    except ImportError:
        return

    app_paths = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
    for root_key in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(root_key, app_paths) as key:
                index = 0
                while True:
                    try:
                        sub_name = winreg.EnumKey(key, index)
                    except OSError:
                        break
                    index += 1
                    try:
                        with winreg.OpenKey(key, sub_name) as sub:
                            value, _ = winreg.QueryValueEx(sub, "")
                            clean = value.strip('"')
                            if clean and os.path.exists(clean):
                                # The registry key is "chrome.exe"; the user
                                # says "chrome".
                                name = sub_name[:-4] if sub_name.lower().endswith(".exe") else sub_name
                                entry = AppEntry(name, [clean], "registry")
                                entries.setdefault(sub_name.lower(), entry)
                                entries.setdefault(name.lower(), entry)
                    except OSError:
                        continue
        except OSError:
            continue

    for folder in (
        os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
        os.path.join(os.environ.get("ProgramData", ""), r"Microsoft\Windows\Start Menu\Programs"),
    ):
        if not folder or not os.path.isdir(folder):
            continue
        for root, _dirs, files in os.walk(folder):
            for filename in files:
                if not filename.lower().endswith(".lnk"):
                    continue
                name = os.path.splitext(filename)[0]
                entry = AppEntry(name, [os.path.join(root, filename)], "startmenu")
                entries.setdefault(name.lower(), entry)
                entries.setdefault(filename.lower(), entry)


def _scan_macos(entries: Dict[str, AppEntry]) -> None:
    """Collects the .app bundles of the Applications folders."""
    folders = ("/Applications", "/System/Applications", os.path.join(os.path.expanduser("~"), "Applications"))
    for folder in folders:
        if not os.path.isdir(folder):
            continue
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        for filename in names:
            if not filename.endswith(".app"):
                continue
            name = filename[: -len(".app")]
            entries.setdefault(name.lower(), AppEntry(name, [os.path.join(folder, filename)], "macos"))


# ─────────────────────────────────────────────────────────────────────────────
# The index
# ─────────────────────────────────────────────────────────────────────────────
class AppIndex:
    """A searchable catalogue of the applications installed on this machine."""

    def __init__(self) -> None:
        self._entries: Dict[str, AppEntry] = {}
        self._scanned = False

    # ── Building ───────────────────────────────────────────────────────────
    def refresh(self) -> int:
        """Rebuilds the index and returns the number of applications found."""
        entries: Dict[str, AppEntry] = {}
        try:
            if IS_WINDOWS:
                _scan_windows(entries)
            elif IS_MACOS:
                _scan_macos(entries)
            else:
                _scan_linux(entries)
        except Exception as e:
            logger.warning(f"Application discovery failed: {e}")

        self._entries = entries
        self._scanned = True
        logger.info(f"Application discovery: {len(entries)} applications indexed.")
        return len(entries)

    def _ensure_scanned(self) -> None:
        if not self._scanned:
            self.refresh()

    # ── Querying ───────────────────────────────────────────────────────────
    def all(self) -> List[AppEntry]:
        """Returns every indexed application, de-duplicated by name."""
        self._ensure_scanned()
        seen = set()
        result = []
        for entry in self._entries.values():
            if entry.name.lower() in seen:
                continue
            seen.add(entry.name.lower())
            result.append(entry)
        return result

    def find(self, query: str) -> Optional[AppEntry]:
        """Finds the application that best matches a spoken name."""
        self._ensure_scanned()
        q = (query or "").lower().strip()
        if not q:
            return None

        if q in self._entries:
            return self._entries[q]

        # A name that starts with the query ("firefox" → "Firefox Beta").
        for key, entry in self._entries.items():
            if key.startswith(q):
                return entry

        # Finally a fuzzy match on the visible name.
        best, score = None, 0.0
        for entry in self.all():
            ratio = difflib.SequenceMatcher(None, q, entry.name.lower()).ratio()
            if q in entry.name.lower():
                ratio = max(ratio, 0.8)
            if ratio > score:
                best, score = entry, ratio
        return best if score >= 0.6 else None

    def search(self, query: str, limit: int = 8) -> List[AppEntry]:
        """Returns the applications whose name contains the query."""
        self._ensure_scanned()
        q = (query or "").lower().strip()
        if not q:
            return []
        matches = [e for e in self.all() if q in e.name.lower()]
        # Real applications come before the raw PATH binaries.
        matches.sort(key=lambda e: (e.source == "path", e.name.lower()))
        return matches[:limit]

    def launch(self, query: str) -> bool:
        """Launches the application that matches the query."""
        entry = self.find(query)
        return entry.launch() if entry else False


#: Shared index used by the launcher and the plugins.
app_index = AppIndex()


def command_for(query: str, *extra: str) -> Optional[List[str]]:
    """
    The command line that starts the application matching `query`, with
    optional extra arguments (a URL, "--incognito", …).

    Start Menu shortcuts are skipped because a ``.lnk`` file cannot take
    arguments; every other source (desktop entry, registry, PATH) can.
    """
    entry = app_index.find(query)
    candidates = ([entry] if entry else []) + [
        e for e in app_index.search(query) if e is not entry
    ]
    for candidate in candidates:
        if candidate.source == "startmenu" or not candidate.args:
            continue
        return [*candidate.args, *extra]
    return None
