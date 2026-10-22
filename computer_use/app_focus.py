"""
PRIVACY68 Application Focus & State Layer.

Every context-aware voice command has to answer two questions before it can
safely act on an application:

    1. "Is the target application running at all?"
    2. "Is it the window the user is looking at right now?"

The answers decide what the command should do:

  * The app is ALREADY the active window  -> do nothing. Do not relaunch it
    (that spawns a second instance, steals focus and costs seconds of dead
    air), and do not wait for a window that is already there.
  * The app is running but in the background -> raise it. No launch needed.
  * The app is not running -> launch it, wait for its window, then raise it.

This is exactly the "open the app ... then use it" flow: the
first command launches the app, and the second one must notice the app is
already up and just use it.

Doing this once, here, means no plugin has to re-implement the Win32 window
dance, and every plugin that talks to an app gets the same "don't relaunch
what is already open" behaviour.

Usage:
    from computer_use.app_focus import AppState, ensure_active, get_state

    state = get_state("vscode", process_hints=("code",))
    if state != AppState.ACTIVE:
        ensure_active("vscode", launch=self._launch_vscode)
"""

import logging
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from core.platform import IS_WINDOWS

logger = logging.getLogger("PRIVACY68.AppFocus")


class AppState:
    """The three states an application window can be in."""

    NOT_RUNNING = "not_running"
    BACKGROUND = "background"
    ACTIVE = "active"

    _DESCRIPTIONS = {
        NOT_RUNNING: "not running",
        BACKGROUND: "running in the background",
        ACTIVE: "active (foreground)",
    }

    @staticmethod
    def describe(state: str) -> str:
        """Human-readable description, for logs and status messages."""
        return AppState._DESCRIPTIONS.get(state, state)


# Browser executables. A browser tab showing a web version of an app (e.g.
# web.whatsapp.com) carries the app's name in its window title, so title-based
# matching must never mistake it for the real desktop application.
_BROWSER_PROCESSES = (
    "chrome.exe",
    "msedge.exe",
    "brave.exe",
    "firefox.exe",
    "opera.exe",
    "vivaldi.exe",
    # The WebView2 renderer is a container, not an application. A UWP app
    # built on WebView2 (the Store build of WhatsApp) has a child window
    # titled after the app; matching on it would pick the renderer instead
    # of the app itself.
    "msedgewebview2.exe",
)

# Shell/host processes. These are CONTAINERS for other windows, never the
# application itself, and they routinely carry the application name in their
# title — a console running a command that mentions "whatsapp" would
# otherwise be mistaken for WhatsApp Desktop, and the automation would type
# into the wrong window.
_HOST_PROCESSES = (
    "cmd.exe",
    "powershell.exe",
    "pwsh.exe",
    "conhost.exe",
    "windowsterminal.exe",
    "windowsterminalserver.exe",
    "openconsole.exe",
    "wt.exe",
    "explorer.exe",
    "python.exe",
    "pythonw.exe",
    # POSIX shells, terminal emulators and the file manager.
    "sh",
    "bash",
    "zsh",
    "fish",
    "dash",
    "gnome-terminal-server",
    "konsole",
    "xfce4-terminal",
    "alacritty",
    "kitty",
    "wezterm-gui",
    "terminator",
    "tilix",
    "nautilus",
    "dolphin",
    "thunar",
    "pcmanfm",
)


def _normalize(tokens: Optional[Iterable[str]]) -> List[str]:
    """Lower-cases and strips a token collection, dropping empties."""
    return [str(t).strip().lower() for t in (tokens or ()) if str(t).strip()]


def _matches(process: str, hints: List[str]) -> bool:
    """True when a process name matches one of the hints (exact or contained)."""
    if not process:
        return False
    for hint in hints:
        if process == hint or hint in process:
            return True
    return False


# Window titles that belong to helper/utility windows rather than to an
# application itself. An app process creates a lot of them ("GDI+ Window",
# "Default IME", tray icons, broadcast receivers) and they can be enumerated
# before the real window, so they must never be focused.
_HELPER_WINDOW_MARKERS = (
    "gdi+ window",
    "default ime",
    "notifyicon",
    ".net-broadcasteventwindow",
    "msctfime",
    "tooltips_class32",
    "ime",
)


def _is_helper_window(title: str) -> bool:
    """True when a window title belongs to a helper/utility window."""
    low = str(title or "").lower().strip()
    if not low:
        return True
    return any(marker in low for marker in _HELPER_WINDOW_MARKERS)


def _enumerate_windows(include_hidden: bool = True) -> List[Dict[str, Any]]:
    """
    Enumerates top-level windows, INCLUDING hidden ones on Windows.

    `WindowManager.list_visible_windows` filters on IsWindowVisible, which
    hides a real problem: a Microsoft Store app (UWP) such as WhatsApp
    Desktop creates its window with a real title but reports
    IsWindowVisible == False until the frame host raises it. A visible-only
    scan therefore reports the Store build of WhatsApp as "not running" even
    while it is running, which is exactly the bug this layer fixes.

    On Linux and macOS the platform layer provides the window list, so the
    same matching logic works everywhere.
    """
    if not IS_WINDOWS:
        from core.platform import list_windows

        return [
            {
                "hwnd": int(w.get("hwnd", 0) or 0),
                "title": str(w.get("title", "")),
                "process_name": str(w.get("process_name", "")),
                "is_visible": True,
                "is_helper": _is_helper_window(str(w.get("title", ""))),
            }
            for w in list_windows()
        ]

    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    try:
        import psutil
    except ImportError:
        psutil = None

    results: List[Dict[str, Any]] = []
    proc_name_cache: Dict[int, str] = {}

    def _proc_for_pid(pid: int) -> str:
        if pid in proc_name_cache:
            return proc_name_cache[pid]
        name = ""
        if psutil:
            try:
                name = psutil.Process(pid).name()
            except Exception:
                name = ""
        proc_name_cache[pid] = name
        return name

    def enum_proc(hwnd, _lparam):
        try:
            if not include_hidden and not user32.IsWindowVisible(hwnd):
                return True

            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value.strip()
            if not title:
                return True

            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            proc = _proc_for_pid(int(pid.value))

            results.append({
                "hwnd": int(hwnd),
                "title": title,
                "process_name": proc,
                "is_visible": bool(user32.IsWindowVisible(hwnd)),
                "is_helper": _is_helper_window(title),
            })
        except Exception:
            pass
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    try:
        user32.EnumWindows(WNDENUMPROC(enum_proc), 0)
    except Exception as e:  # pragma: no cover - defensive
        logger.debug(f"AppFocus: window enumeration failed: {e}")

    return results


def _match_window(
    app_name: str,
    title_hints: Optional[Iterable[str]] = None,
    process_hints: Optional[Iterable[str]] = None,
    exclude_processes: Optional[Iterable[str]] = None,
) -> Tuple[int, str]:
    """
    Finds the window belonging to an application.

    Returns (hwnd, process_name). hwnd is 0 when the application is not
    running.

    Matching order:
      1. Process name AND app title — the strongest signal.
      2. Process name. This is the only reliable discriminator when an app
         also exists on the web (WhatsApp Desktop vs. web.whatsapp.com in a
         browser tab).
      3. Window title, excluding browsers and console/host windows.

    Helper windows (IME, GDI+, tray icons) are never considered, so the
    match does not depend on the order Windows happens to enumerate
    windows in.

    Deliberately does NOT fall back to the shared WindowManager's loose
    substring title search: that matches a console window whose title
    happens to mention the app, which would make the automation act on the
    wrong window. A wrong window is far worse than a missed match here.
    """
    procs = _normalize(process_hints)
    titles = _normalize(title_hints)
    excluded = _normalize(exclude_processes) or list(_BROWSER_PROCESSES)
    # Hosts are always excluded, whatever the caller passes.
    excluded = list(dict.fromkeys(excluded + list(_HOST_PROCESSES)))

    windows = _enumerate_windows(include_hidden=True)

    # Helper windows never count as "the application window".
    candidates = [w for w in windows if not w.get("is_helper")]
    if not candidates:
        candidates = windows

    # 1. Process name AND a title that names the app. This is the strongest
    #    signal: the window really belongs to the app AND is its main window.
    if procs and titles:
        for win in candidates:
            proc = str(win.get("process_name", "")).lower()
            title = str(win.get("title", "")).lower().strip()
            if _matches(proc, procs) and any(title == t or title.startswith(t) for t in titles):
                return int(win["hwnd"]), proc

    # 2. Process name alone (authoritative when the caller supplies hints).
    if procs:
        for win in candidates:
            proc = str(win.get("process_name", "")).lower()
            if _matches(proc, procs):
                return int(win["hwnd"]), proc

    # 3. Window title, ignoring browsers and host/console windows.
    for win in candidates:
        proc = str(win.get("process_name", "")).lower()
        if _matches(proc, excluded):
            continue
        title = str(win.get("title", "")).lower().strip()
        if titles and any(title == t or title.startswith(t) for t in titles):
            return int(win["hwnd"]), proc

    return 0, ""


def get_state(
    app_name: str,
    title_hints: Optional[Iterable[str]] = None,
    process_hints: Optional[Iterable[str]] = None,
    exclude_processes: Optional[Iterable[str]] = None,
) -> str:
    """
    Returns the current state of an application: ACTIVE, BACKGROUND or
    NOT_RUNNING.
    """
    hwnd, _ = _match_window(app_name, title_hints, process_hints, exclude_processes)
    if not hwnd:
        return AppState.NOT_RUNNING

    from computer_use.window_manager import window_manager

    procs = _normalize(process_hints)

    try:
        active_hwnd = int(window_manager.get_active_hwnd() or 0)
    except Exception:
        active_hwnd = 0

    if active_hwnd and active_hwnd == hwnd:
        return AppState.ACTIVE

    # Some apps host their real window inside a frame, so the HWND may differ
    # while the foreground window still belongs to the same application.
    # Compare the PROCESS of the foreground window rather than its title:
    # a console whose title mentions the app is not the app.
    if procs:
        try:
            active_proc = str(window_manager.get_process_name_for_hwnd(active_hwnd)).lower()
            if active_proc and _matches(active_proc, procs):
                return AppState.ACTIVE
        except Exception:
            pass

    return AppState.BACKGROUND


def focus_existing(
    app_name: str,
    title_hints: Optional[Iterable[str]] = None,
    process_hints: Optional[Iterable[str]] = None,
    exclude_processes: Optional[Iterable[str]] = None,
) -> bool:
    """
    Raises an already-running application to the foreground.
    Returns False when the application is not running (nothing to focus).
    """
    from computer_use.window_manager import window_manager

    hwnd, _ = _match_window(app_name, title_hints, process_hints, exclude_processes)
    if not hwnd:
        return False

    if not window_manager.focus_window(hwnd):
        return False

    time.sleep(0.15)
    return True


def ensure_active(
    app_name: str,
    launch: Optional[Callable[[], bool]] = None,
    title_hints: Optional[Iterable[str]] = None,
    process_hints: Optional[Iterable[str]] = None,
    exclude_processes: Optional[Iterable[str]] = None,
    wait_timeout: float = 8.0,
    poll_interval: float = 0.25,
    require_window: bool = True,
) -> bool:
    """
    Guarantees that an application is running AND is the foreground window.

    * Already active      -> returns True immediately (nothing is launched).
    * Running, background -> the window is raised, nothing is launched.
    * Not running         -> `launch` is called, then the window is waited for
                            and raised.

    `launch` may be None when the caller has already started the app and only
    needs this function to wait for the window to appear.

    `require_window` decides what counts as success:
      True  (default) — the application must present a window before this
                        returns True. Use this before typing into the app.
      False — a successful LAUNCH is enough. Use this for "open X", where the
                        app may still be starting up and the caller does not
                        need to interact with it yet.
    """
    state = get_state(app_name, title_hints, process_hints, exclude_processes)

    if state == AppState.ACTIVE:
        logger.debug(f"AppFocus: '{app_name}' is already the active window — not relaunching.")
        return True

    from computer_use.window_manager import window_manager

    if state == AppState.BACKGROUND:
        logger.info(f"AppFocus: '{app_name}' is running in the background — raising it.")
        if focus_existing(app_name, title_hints, process_hints, exclude_processes):
            return True
        logger.debug(f"AppFocus: could not raise '{app_name}' — attempting to launch it again.")

    # Not running (or the raise failed) — start it.
    launched = False
    if launch is not None:
        logger.info(f"AppFocus: '{app_name}' is {AppState.describe(state)} — launching it.")
        try:
            launched = bool(launch())
        except Exception as e:
            logger.error(f"AppFocus: launching '{app_name}' failed: {e}")
            return False

        if not launched:
            # The launcher itself failed. Waiting for a window that can never
            # appear would only add dead air, so stop here.
            logger.warning(f"AppFocus: launching '{app_name}' did not report success.")
            return False

    # Wait for the window to show up. The app may already be starting up.
    deadline = time.time() + max(0.0, wait_timeout)
    hwnd = 0
    while time.time() < deadline:
        hwnd, _ = _match_window(app_name, title_hints, process_hints, exclude_processes)
        if hwnd:
            break
        time.sleep(poll_interval)

    if not hwnd:
        if not require_window:
            # The caller only asked for the app to be started.
            logger.info(
                f"AppFocus: '{app_name}' was launched but its window has not appeared yet."
            )
            return True
        logger.warning(
            f"AppFocus: '{app_name}' did not present a window within {wait_timeout:.0f}s."
        )
        return False

    try:
        window_manager.focus_window(hwnd)
    except Exception as e:  # pragma: no cover - defensive
        logger.debug(f"AppFocus: focus failed for '{app_name}': {e}")
    time.sleep(0.15)
    return True
