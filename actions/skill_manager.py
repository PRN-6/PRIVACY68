import logging
from skills.chrome import Chrome
from skills.web_search import WebSearch
from plugins.manager import plugin_manager

logger = logging.getLogger("PRIVACY68.SkillManager")

class SkillManager:
    def __init__(self):
        self.active_skills = [
            Chrome(),
            WebSearch(),
        ]
        logger.info(f"SkillManager initialized with {len(self.active_skills)} skills + {len(plugin_manager.get_all_plugins())} plugins.")

    def get_all_intents(self) -> dict:
        """Collects fast-lane training phrases from active skills and enabled plugins."""
        intents_dict = {}
        for skill in self.active_skills:
            intents_dict[skill.name] = skill.fast_intents
            
        # Merge plugin intents
        intents_dict.update(plugin_manager.get_active_fast_intents())
        return intents_dict

    def get_system_prompt_descriptions(self) -> str:
        """Collects descriptions for Ollama's system prompt."""
        descriptions = []
        for skill in self.active_skills:
            descriptions.append(skill.description)
            
        # Merge plugin descriptions
        plugin_descs = plugin_manager.get_active_system_descriptions()
        if plugin_descs:
            descriptions.append(plugin_descs)
            
        return "\n".join(descriptions)

    def execute_skill(self, tool_name: str, text: str) -> bool:
        """Finds the correct skill or plugin action and executes it."""
        for skill in self.active_skills:
            if skill.name == tool_name:
                return skill.execute(text)
                
        # Check direct plugin action (e.g. 'ppt.open', 'whatsapp.send_message')
        if plugin_manager.execute_action(tool_name, text):
            return True

        # AI name fallback mapping (e.g. if Ollama selected 'PowerPoint' instead of 'ppt.open')
        normalized = tool_name.lower().strip().replace(" ", "").replace("_", "").replace(".", "")
        if "powerpoint" in normalized or normalized == "ppt":
            return plugin_manager.execute_action("ppt.open", text)
        elif "whatsapp" in normalized:
            return plugin_manager.execute_action("whatsapp.open", text)
        elif "chrome" in normalized:
            return plugin_manager.execute_action("chrome.open", text)
        elif "notepad" in normalized:
            return plugin_manager.execute_action("notepad.open", text)
        elif "gesture" in normalized or "handgesture" in normalized or "webcam" in normalized:
            # AI often returns 'Gestures' / 'Hand Gestures' without enable/disable
            intent_text = text.lower()
            if any(w in intent_text for w in ("disable", "stop", "turn off", "turnoff", "deactivate", "off")):
                return plugin_manager.execute_action("gesture.disable", text)
            return plugin_manager.execute_action("gesture.enable", text)

    def execute_tool_with_args(self, tool_name: str, args: dict, raw_text: str = "") -> bool:
        """
        Executes a tool call using structured arguments extracted by Hermes Agent.
        """
        clean_tool = tool_name.lower().strip()

        # 1. Open App / Desktop Launcher
        if clean_tool in ("open_app", "launch_app", "app.open"):
            app_name = (args.get("app_name") or raw_text).lower().strip()
            if "chrome" in app_name:
                return plugin_manager.execute_action("chrome.open", raw_text) or self.execute_skill("chrome", raw_text)
            elif "brave" in app_name:
                return plugin_manager.execute_action("brave.open", raw_text)
            elif "vscode" in app_name or "code" in app_name:
                return plugin_manager.execute_action("vscode.open", raw_text)
            elif "notepad" in app_name:
                return plugin_manager.execute_action("notepad.open", raw_text)
            elif "powerpoint" in app_name or "ppt" in app_name:
                return plugin_manager.execute_action("ppt.open", raw_text)
            elif "whatsapp" in app_name:
                return plugin_manager.execute_action("whatsapp.open", raw_text)
            else:
                return self.execute_skill(app_name, raw_text)

        # 2. Web Search / Knowledge Lookups
        elif clean_tool in ("web_search", "google_search", "search_web"):
            query = args.get("query") or raw_text
            for skill in self.active_skills:
                if skill.name == "web_search":
                    return skill.execute(query)
            return self.execute_skill("web_search", query)

        # 3. WhatsApp Messaging & Chats
        elif clean_tool in ("whatsapp_send", "whatsapp.send_message", "whatsapp_message"):
            contact = args.get("contact", "")
            message = args.get("message", "")
            cmd_text = f"send message to {contact} saying {message}" if message else f"open chat with {contact}"
            return plugin_manager.execute_action("whatsapp.send_message", cmd_text) or plugin_manager.execute_action("whatsapp.open", raw_text)

        # 4. PowerPoint Control
        elif clean_tool in ("powerpoint_control", "ppt_control", "ppt"):
            action = (args.get("action") or "").lower().strip()
            slide_num = args.get("slide_number")
            if "next" in action:
                return plugin_manager.execute_action("ppt.next", raw_text)
            elif "prev" in action or "back" in action:
                return plugin_manager.execute_action("ppt.previous", raw_text)
            elif "start" in action:
                return plugin_manager.execute_action("ppt.start_slideshow", raw_text)
            elif "end" in action or "stop" in action:
                return plugin_manager.execute_action("ppt.end_slideshow", raw_text)
            elif "laser" in action:
                return plugin_manager.execute_action("ppt.laser", raw_text)
            elif "pen" in action:
                return plugin_manager.execute_action("ppt.pen", raw_text)
            elif "black" in action:
                return plugin_manager.execute_action("ppt.black_screen", raw_text)
            elif "white" in action:
                return plugin_manager.execute_action("ppt.white_screen", raw_text)
            elif slide_num is not None:
                return plugin_manager.execute_action("ppt.goto_slide", f"slide {slide_num}")
            return plugin_manager.execute_action("ppt.open", raw_text)

        # 5. Hand Gestures Control
        elif clean_tool in ("gesture_control", "gesture", "gestures"):
            action = (args.get("action") or raw_text).lower().strip()
            if any(w in action for w in ("disable", "stop", "off", "turn off", "deactivate")):
                return plugin_manager.execute_action("gesture.disable", raw_text)
            return plugin_manager.execute_action("gesture.enable", raw_text)

        # 6. Windows System Control
        elif clean_tool in ("system_control", "system"):
            cmd = (args.get("command") or raw_text).lower().strip()
            if "up" in cmd:
                return plugin_manager.execute_action("system.volume_up", raw_text)
            elif "down" in cmd:
                return plugin_manager.execute_action("system.volume_down", raw_text)
            elif "mute" in cmd:
                return plugin_manager.execute_action("system.volume_mute", raw_text)
            elif "lock" in cmd:
                return plugin_manager.execute_action("system.lock", raw_text)
            elif "sleep" in cmd:
                return plugin_manager.execute_action("system.sleep", raw_text)
            return plugin_manager.execute_action("system.volume_up", raw_text)

        # 7. Generic Dynamic Plugin Handler (e.g. 'plugin_spotify_main_action', 'plugin_discord_open')
        elif clean_tool.startswith("plugin_"):
            raw_action = clean_tool[7:]  # strip 'plugin_' prefix
            dot_action = raw_action.replace("_", ".", 1)
            inp_text = args.get("input_text") or args.get("command") or raw_text
            if plugin_manager.execute_action(dot_action, inp_text):
                return True
            if plugin_manager.execute_action(raw_action, inp_text):
                return True
            # Fallback to main_action for custom user-created plugins
            if plugin_manager.execute_action(f"{raw_action}.main_action", inp_text):
                return True

        # Fallback to standard execute_skill
        return self.execute_skill(tool_name, raw_text)

# Create a global instance that executor.py and router.py will use
manager = SkillManager()
