"""
Browser engine detection for the PRIVACY68 Control Center.

The Control Center is rendered by pywebview, which uses the platform's native
web engine:

  * Windows — the Edge WebView2 Runtime (Chromium)
  * Linux   — WebKitGTK (GTK/Qt) or a Chromium engine, depending on the
              pywebview GUI backend that is installed
  * macOS   — WKWebView, which is part of the operating system

On Windows the WebView2 runtime is a hard requirement: without it pywebview
spends 30-60 seconds probing the registry for a Chromium engine and then
silently falls back to the deprecated MSHTML engine, which cannot parse the
modern JavaScript and Tailwind bundle the dashboard is built from. The user
sees a blank white window that never finishes loading and assumes the app is
broken. These helpers let PRIVACY68 detect the runtime up-front so the app
can report the problem immediately, with a download link.

On Linux and macOS the engine ships with the system, so the check simply
reports which backend is available.
"""

import logging
import os
import shutil
from typing import Any, Dict, List, Optional, Tuple

from core.platform import IS_LINUX, IS_MACOS, IS_WINDOWS

logger = logging.getLogger("PRIVACY68.WebView2")

# Product GUID of the Evergreen WebView2 Runtime inside the EdgeUpdate registry.
WEBVIEW2_CLIENT_GUID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

# Oldest runtime able to render the dashboard (Chromium 86+).
WEBVIEW2_MIN_VERSION: Tuple[int, ...] = (86, 0, 622, 0)

# Official Evergreen bootstrapper. It installs per-machine when the user is an
# administrator and falls back to a per-user install otherwise, which is why it
# is the right artifact for the low-privilege Inno Setup installer.
WEBVIEW2_DOWNLOAD_URL = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"

# Direct link to the offline x64 installer, offered when the user prefers to
# download the runtime manually.
WEBVIEW2_OFFLINE_INSTALLER_URL = "https://go.microsoft.com/fwlink/p/?LinkId=2124705"


def _candidate_registry_paths() -> List[Tuple[int, str]]:
    """Registry locations where the EdgeUpdate client entries may live."""
    import winreg

    base = rf"Microsoft\EdgeUpdate\Clients\{WEBVIEW2_CLIENT_GUID}"
    return [
        (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\{base}"),
        (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\WOW6432Node\{base}"),
        (winreg.HKEY_CURRENT_USER, rf"SOFTWARE\{base}"),
    ]


def parse_version(value: Any) -> Optional[Tuple[int, ...]]:
    """Parses a dotted version string into a comparable tuple of ints."""
    if value is None:
        return None
    parts: List[int] = []
    for chunk in str(value).strip().split("."):
        chunk = chunk.strip()
        if not chunk.isdigit():
            break
        parts.append(int(chunk))
    return tuple(parts) if parts else None


def version_at_least(version: Any, minimum: Tuple[int, ...] = WEBVIEW2_MIN_VERSION) -> bool:
    """True when `version` is greater than or equal to `minimum`."""
    parsed = parse_version(version)
    if not parsed:
        return False
    padded = parsed + (0,) * (len(minimum) - len(parsed))
    return padded >= minimum


def get_webview2_version() -> Optional[str]:
    """Returns the newest WebView2 runtime version reported by the registry."""
    if not IS_WINDOWS:
        return None
    try:
        import winreg
    except ImportError:
        return None

    best: Optional[Tuple[Tuple[int, ...], str]] = None
    for hive, path in _candidate_registry_paths():
        try:
            with winreg.OpenKey(hive, path) as key:
                raw, _ = winreg.QueryValueEx(key, "pv")
        except OSError:
            continue
        parsed = parse_version(raw)
        if parsed and (best is None or parsed > best[0]):
            best = (parsed, str(raw))
    return best[1] if best else None


def _find_evergreen_installation() -> Optional[str]:
    """
    Filesystem fallback for machines where the EdgeUpdate registry entries are
    missing or locked down by group policy.
    """
    roots: List[str] = []
    for env_var in ("ProgramFiles(x86)", "ProgramFiles", "LocalAppData"):
        base = os.environ.get(env_var)
        if base:
            roots.append(os.path.join(base, "Microsoft", "EdgeWebView", "Application"))

    best: Optional[Tuple[Tuple[int, ...], str]] = None
    for root in roots:
        try:
            entries = os.listdir(root)
        except OSError:
            continue
        for entry in entries:
            parsed = parse_version(entry)
            if parsed and (best is None or parsed > best[0]):
                exe = os.path.join(root, entry, "msedgewebview2.exe")
                if os.path.exists(exe):
                    best = (parsed, entry)
    return best[1] if best else None


def is_webview2_installed() -> bool:
    """True when a WebView2 runtime new enough for the dashboard is present."""
    if not IS_WINDOWS:
        return True
    registry_version = get_webview2_version()
    if registry_version and version_at_least(registry_version):
        return True
    fs_version = _find_evergreen_installation()
    return bool(fs_version) and version_at_least(fs_version)


def _linux_web_engine() -> Dict[str, Any]:
    """Detects the browser engine pywebview can use on Linux."""
    candidates = {
        "gtk": ["libwebkit2gtk-4.1.so.0", "libwebkit2gtk-4.0.so.0"],
        "qt": ["libQt6WebEngineCore.so.6", "libQt5WebEngineWidgets.so.5"],
        "cef": ["libcef.so", "libcef_dll_wrapper.so"],
        "gtk3": ["libwebkit2gtk-4.1.so.0"],
    }
    search_dirs = [
        "/usr/lib",
        "/usr/lib64",
        "/usr/lib/x86_64-linux-gnu",
        "/usr/lib/aarch64-linux-gnu",
        "/usr/local/lib",
    ]
    for engine, libraries in candidates.items():
        for library in libraries:
            for folder in search_dirs:
                if os.path.exists(os.path.join(folder, library)):
                    return {"engine": engine, "library": library}
    # QtWebEngine via the runtime loader.
    if shutil.which("qmlscene") or shutil.which("qml"):
        return {"engine": "qt", "library": "qt (runtime detected)"}
    return {"engine": "", "library": ""}


def get_webview2_status() -> Dict[str, Any]:
    """
    Full status of the browser engine that will render the Control Center.

    The key `installed` reports whether the dashboard can be shown at all.
    """
    if IS_LINUX:
        engine = _linux_web_engine()
        return {
            "installed": bool(engine["engine"]),
            "version": engine["engine"] or None,
            "registry_version": None,
            "filesystem_version": engine["library"] or None,
            "min_version": "webkit2gtk-4.0 / QtWebEngine",
            "download_url": "https://packages.debian.org/stable/libwebkit2gtk-4.0-37",
            "offline_installer_url": "https://wiki.archlinux.org/title/WebKitGTK",
            "engine": engine["engine"] or "unknown",
        }

    if IS_MACOS:
        return {
            "installed": True,
            "version": "WKWebView",
            "registry_version": None,
            "filesystem_version": "WKWebView (system)",
            "min_version": "system",
            "download_url": "",
            "offline_installer_url": "",
            "engine": "wkwebview",
        }

    registry_version = get_webview2_version()
    fs_version = _find_evergreen_installation()
    effective = registry_version or fs_version
    installed = bool(effective) and version_at_least(effective)
    return {
        "installed": installed,
        "version": effective,
        "registry_version": registry_version,
        "filesystem_version": fs_version,
        "min_version": ".".join(str(p) for p in WEBVIEW2_MIN_VERSION),
        "download_url": WEBVIEW2_DOWNLOAD_URL,
        "offline_installer_url": WEBVIEW2_OFFLINE_INSTALLER_URL,
        "engine": "webview2",
    }


def get_webview2_install_hint() -> str:
    """User-facing explanation of how to install the missing WebView2 runtime."""
    if IS_LINUX:
        return (
            "The PRIVACY68 Control Center needs a browser engine, and none was "
            "found on this system.\n\n"
            "Install WebKitGTK (the backend pywebview uses on Linux):\n\n"
            "  Debian / Ubuntu:  sudo apt install libwebkit2gtk-4.0-37\n"
            "  Fedora:           sudo dnf install webkit2gtk4.1\n"
            "  Arch:             sudo pacman -S webkit2gtk-4.1\n\n"
            "After installing, reopen the Control Center."
        )
    if IS_MACOS:
        return (
            "The PRIVACY68 Control Center could not find a usable web engine.\n\n"
            "macOS ships WKWebView with the system, so this usually means a "
            "damaged pywebview installation. Reinstall the dependencies:\n\n"
            "  pip install --upgrade pywebview\n\n"
            "After that, reopen the Control Center."
        )
    return (
        "The PRIVACY68 Control Center needs the Microsoft Edge WebView2 Runtime, "
        "which is not installed on this PC.\n\n"
        "Windows 10 and 11 normally include it, but some editions (LTSC, "
        "Enterprise, freshly imaged or debloated PCs) do not. Without it the "
        "Control Center opens as a blank window and never finishes loading.\n\n"
        f"Download the runtime here:\n{WEBVIEW2_DOWNLOAD_URL}\n\n"
        "After installing, reopen the Control Center."
    )
