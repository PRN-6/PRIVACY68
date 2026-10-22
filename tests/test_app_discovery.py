"""
Tests for the application discovery layer.

The assistant must be able to open any application the user has installed,
so `core/apps.py` indexes what is on the machine and the command catalogue
learns those names. These tests cover the parsing, the matching and the
catalogue wiring — the scanning itself only touches the real machine.
"""

import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.apps import AppEntry, AppIndex, parse_exec


class TestExecParsing(unittest.TestCase):
    """A desktop `Exec=` line must become a runnable argument list."""

    def test_plain_command(self):
        self.assertEqual(parse_exec("firefox"), ["firefox"])

    def test_field_codes_are_removed(self):
        self.assertEqual(
            parse_exec("firefox %u"),
            ["firefox"],
        )
        self.assertEqual(
            parse_exec("gedit %U"),
            ["gedit"],
        )

    def test_field_code_glued_to_an_argument(self):
        self.assertEqual(
            parse_exec("libreoffice --writer --file=%F"),
            ["libreoffice", "--writer", "--file="],
        )

    def test_flatpak_arguments_are_kept(self):
        self.assertEqual(
            parse_exec("/usr/bin/flatpak run --branch=stable com.example.App %U"),
            ["/usr/bin/flatpak", "run", "--branch=stable", "com.example.App"],
        )

    def test_env_wrapper_is_skipped(self):
        self.assertEqual(
            parse_exec("env LANG=en_US.UTF-8 /opt/app/bin/app --flag %F"),
            ["/opt/app/bin/app", "--flag"],
        )

    def test_quoted_path_with_spaces(self):
        self.assertEqual(
            parse_exec('"/opt/My Apps/app" --go'),
            ["/opt/My Apps/app", "--go"],
        )


class TestAppIndex(unittest.TestCase):
    """The index must find an application by the name the user speaks."""

    def setUp(self):
        self.index = AppIndex()
        self.index._entries = {
            "firefox": AppEntry("Firefox", ["/usr/bin/firefox"], "desktop"),
            "firefox-esr": AppEntry("Firefox ESR", ["/usr/bin/firefox-esr"], "desktop"),
            "code": AppEntry("Visual Studio Code", ["/usr/bin/code"], "path"),
        }
        self.index._scanned = True

    def test_exact_match(self):
        entry = self.index.find("firefox")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.name, "Firefox")

    def test_case_is_ignored(self):
        self.assertEqual(self.index.find("FireFox").name, "Firefox")

    def test_prefix_match(self):
        self.assertEqual(self.index.find("fire").name, "Firefox")

    def test_fuzzy_match(self):
        self.assertEqual(self.index.find("firefo").name, "Firefox")

    def test_unknown_name_returns_nothing(self):
        self.assertIsNone(self.index.find("definitely not installed"))

    def test_empty_query_returns_nothing(self):
        self.assertIsNone(self.index.find(""))
        self.assertIsNone(self.index.find("   "))

    def test_search_returns_partial_matches(self):
        names = [e.name for e in self.index.search("fire")]
        self.assertIn("Firefox", names)
        self.assertIn("Firefox ESR", names)

    def test_all_is_deduplicated_by_name(self):
        # "firefox" is indexed under two keys but is one application.
        names = [e.name for e in self.index.all()]
        self.assertEqual(len(names), len(set(names)))


class TestCatalogueWiring(unittest.TestCase):
    """The fast lane must recognise the applications of this computer."""

    def test_register_installed_apps_teaches_the_catalogue(self):
        from actions.catalog import register_installed_apps
        from actions.registry import LANE_FAST, registry
        import core.apps as apps_module

        index = AppIndex()
        index._entries = {"myeditor": AppEntry("My Editor", ["/usr/bin/myeditor"], "desktop")}
        index._scanned = True

        original = apps_module.app_index
        try:
            apps_module.app_index = index
            added = register_installed_apps()
        finally:
            apps_module.app_index = original

        self.assertEqual(added, 1)

        match = registry.match("open my editor", lane=LANE_FAST)
        self.assertIsNotNone(match, "The installed application was not recognised")
        self.assertEqual(match.spec.id, "system.application")
        self.assertEqual(match.slots.get("name", "").lower(), "my editor")

    def test_the_known_applications_still_work(self):
        """Merging the installed names must not break the shipped ones."""
        from actions.registry import LANE_FAST, registry

        match = registry.match("open chrome", lane=LANE_FAST)
        self.assertIsNotNone(match)
        self.assertEqual(match.spec.id, "system.application")


if __name__ == "__main__":
    unittest.main()
