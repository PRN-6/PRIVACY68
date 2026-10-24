import os
import tempfile
import unittest

from plugins.base_plugin import BasePlugin
from plugins.manager import PluginManager


class TestPluginManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.manager = PluginManager.__new__(PluginManager)
        self.manager.plugins = {}
        self.manager.plugin_paths = {}
        self.manager.plugin_mtimes = {}
        self.manager.plugin_dir = self.temp_dir.name
        self.manager.last_error = ""

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_template_escapes_text_and_registers_generated_plugin(self):
        path = self.manager.create_plugin_template(
            "sample_plugin",
            'Plugin "One"',
            "🔌",
            'Description with "quotes"',
            "unused",
        )

        plugin = self.manager.get_plugin("sample_plugin")
        self.assertTrue(os.path.isfile(path))
        self.assertIsNotNone(plugin)
        self.assertEqual(plugin.name, 'Plugin "One"')
        self.assertEqual(plugin.description, 'Description with "quotes"')
        self.assertFalse(plugin.is_builtin)

    def test_plugin_identifier_is_validated(self):
        with self.assertRaises(ValueError):
            self.manager.create_plugin_template("../bad", "Bad", "🔌", "Bad plugin", "")

    def test_install_and_uninstall_external_plugin_file(self):
        source_dir = tempfile.TemporaryDirectory()
        self.addCleanup(source_dir.cleanup)
        source_path = os.path.join(source_dir.name, "custom_plugin.py")
        with open(source_path, "w", encoding="utf-8") as plugin_file:
            plugin_file.write(
                "from plugins.base_plugin import BasePlugin\n"
                "class CustomPlugin(BasePlugin):\n"
                "    def execute(self, action, **kwargs):\n"
                "        return True\n"
            )

        manager_dir = os.path.join(self.temp_dir.name, "installed")
        os.mkdir(manager_dir)
        self.manager.plugin_dir = manager_dir
        self.assertTrue(self.manager.install_plugin_from_file(source_path))
        installed_path = self.manager.plugin_paths["custom"]
        registered_plugin = self.manager.get_plugin("custom")
        self.assertTrue(self.manager.set_plugin_enabled("custom", False))
        self.manager.load_external_plugins()
        self.assertIs(self.manager.get_plugin("custom"), registered_plugin)
        self.assertFalse(self.manager.get_plugin("custom").is_enabled)
        self.assertTrue(os.path.isfile(installed_path))
        self.assertTrue(self.manager.uninstall_plugin("custom"))
        self.assertFalse(os.path.exists(installed_path))
        self.assertIsNone(self.manager.get_plugin("custom"))

    def test_builtin_cannot_be_uninstalled_and_unknown_plugin_cannot_be_enabled(self):
        class BuiltinPlugin(BasePlugin):
            def execute(self, action, **kwargs):
                return True

        self.manager.register_plugin(BuiltinPlugin(), is_builtin=True)
        self.assertFalse(self.manager.uninstall_plugin("builtin"))
        self.assertFalse(self.manager.set_plugin_enabled("missing", True))
        self.assertTrue(self.manager.set_plugin_enabled("builtin", False))
        self.assertFalse(self.manager.get_plugin("builtin").is_enabled)

    def test_core_plugins_are_registered_with_dashboard_metadata(self):
        self.manager.load_builtin_plugins()
        plugins = {plugin.id: plugin for plugin in self.manager.get_all_plugins()}

        self.assertEqual(set(plugins), {"chrome", "system", "whatsapp"})
        self.assertTrue(all(plugin.is_builtin for plugin in plugins.values()))
        self.assertTrue(all(plugin.is_enabled for plugin in plugins.values()))


if __name__ == "__main__":
    unittest.main()
