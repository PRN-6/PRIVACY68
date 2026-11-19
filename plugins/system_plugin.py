"""
Windows System Control Plugin Adapter.
Bridges legacy BasePlugin interface to modern services.system.SystemService.
"""

from plugins.base_plugin import BasePlugin
from services.system import SystemService, system_service


class SystemPlugin(SystemService, BasePlugin):
    """Legacy plugin wrapper delegating to services.system.SystemService."""

    def __init__(self):
        BasePlugin.__init__(self)
        SystemService.__init__(self)
        self.is_builtin = True
