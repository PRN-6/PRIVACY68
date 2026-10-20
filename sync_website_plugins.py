"""
Sync plugin sources into the website download folder.

The website (website/plugins.html) serves plugin .py files directly to end
users from website/downloads/plugins/. Those copies were previously maintained
by hand, which silently drifted from the canonical sources in extra_plugins/
and plugins/.

This script regenerates them from the canonical source so the two can never
diverge. Run it after changing any plugin, or let build.bat do it for you.

It only ever copies files forward — it never deletes anything.

The set of plugins to sync is derived from the download links in
website/plugins.html, so adding a plugin to the site page automatically
includes it here.

Usage:
    python sync_website_plugins.py          # sync and report
    python sync_website_plugins.py --check  # exit 1 if anything is out of date
"""

import filecmp
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DEST_DIR = os.path.join(ROOT, "website", "downloads", "plugins")
PLUGINS_PAGE = os.path.join(ROOT, "website", "plugins.html")

# Canonical source dirs, in priority order:
#   extra_plugins/  : plugin marketplace entries shipped for download
#   plugins/        : built-in plugins (chrome, system) also offered on the site
SOURCE_DIRS = [
    os.path.join(ROOT, "extra_plugins"),
    os.path.join(ROOT, "plugins"),
]

# Package plumbing and non-plugin modules that are not downloadable plugins
SKIP_FILES = {
    "__init__.py",
    "base_plugin.py",
    "manager.py",
    "profile_manager.py",
    "win_keys.py",
    "win_utils.py",
}


def website_plugin_names():
    """Plugin filenames the website actually offers for download."""
    if not os.path.isfile(PLUGINS_PAGE):
        return set()
    with open(PLUGINS_PAGE, encoding="utf-8") as f:
        html = f.read()
    return set(re.findall(r"downloads/plugins/([A-Za-z0-9_]+\.py)", html))


def collect_sources():
    """Map plugin filename -> source path (first match wins)."""
    wanted = website_plugin_names()
    if not wanted:
        print(f"[ERROR] Could not read plugin download links from {PLUGINS_PAGE}")
        return {}

    sources = {}
    for src_dir in SOURCE_DIRS:
        if not os.path.isdir(src_dir):
            continue
        for fn in sorted(wanted):
            if fn in SKIP_FILES or fn.startswith("_"):
                continue
            candidate = os.path.join(src_dir, fn)
            if os.path.isfile(candidate):
                sources.setdefault(fn, candidate)
    return sources


def main() -> int:
    check_only = "--check" in sys.argv

    if not os.path.isdir(DEST_DIR):
        if check_only:
            print(f"[MISSING] Website plugin folder not found: {DEST_DIR}")
            return 1
        os.makedirs(DEST_DIR, exist_ok=True)
        print(f"[OK] Created {DEST_DIR}")

    sources = collect_sources()
    if not sources:
        print("[ERROR] No plugin sources found to sync.")
        return 1

    out_of_date = []
    for fn, src_path in sources.items():
        dest_path = os.path.join(DEST_DIR, fn)
        if os.path.exists(dest_path) and filecmp.cmp(src_path, dest_path, shallow=False):
            continue
        out_of_date.append(fn)
        if not check_only:
            shutil.copy2(src_path, dest_path)
            rel = os.path.relpath(src_path, ROOT)
            print(f"[SYNCED] {fn}  <- {rel}")

    if not out_of_date:
        print(f"[OK] All {len(sources)} website plugin copies are up to date.")
        return 0

    if check_only:
        print(f"[STALE] {len(out_of_date)} file(s) out of date: {', '.join(out_of_date)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
