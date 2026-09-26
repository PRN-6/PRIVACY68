"""
Privacy68 Computer Use & Desktop Control Layer.
Provides native Windows accessibility (UIA), window management,
observer, launcher, system tools, and unified safe action primitives.
"""

from computer_use.window_manager import WindowManager, window_manager
from computer_use.windows_uia import WindowsUIA, uia_engine
from computer_use.launcher import AppLauncher, app_launcher
from computer_use.observer import DesktopObserver, desktop_observer
from computer_use.actions import ComputerActions, computer_actions
from computer_use.system_tools import (
    create_folder,
    create_file,
    rename_item,
    delete_file,
    move_item,
    open_settings,
    open_web_or_search,
    open_application,
    open_path,
    list_directory,
    verify_path_exists,
    system_action,
    get_desktop_path,
    get_documents_path,
    get_downloads_path,
    get_pictures_path,
    resolve_path,
    SETTINGS_PAGES,
)

__all__ = [
    "WindowManager",
    "window_manager",
    "WindowsUIA",
    "uia_engine",
    "AppLauncher",
    "app_launcher",
    "DesktopObserver",
    "desktop_observer",
    "ComputerActions",
    "computer_actions",
    "create_folder",
    "create_file",
    "rename_item",
    "delete_file",
    "move_item",
    "open_settings",
    "open_web_or_search",
    "open_application",
    "open_path",
    "list_directory",
    "verify_path_exists",
    "system_action",
    "get_desktop_path",
    "get_documents_path",
    "get_downloads_path",
    "get_pictures_path",
    "resolve_path",
    "SETTINGS_PAGES",
]
