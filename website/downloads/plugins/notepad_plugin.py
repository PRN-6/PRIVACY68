import logging
from plugins.base_plugin import BasePlugin
from typing import Dict,List,Callable
import subprocess
from plugins.win_keys import kill_process

logger = logging.getLogger("PRIVACY68.Plugin.Notepad")

class NotepadPluggin(BasePlugin):
    #this plugin opens and closes notepad
    id = "notepad"
    name = "Notepad"
    icon = "📝"
    description ="notepad , plugin"
    version ="1.0.0"
    author="prinson"
    is_builtin = False

    #action mapping 
    @property
    def actions(self) -> Dict[str,Callable[[str],bool]]:
        return{
            "notepad.open":self.open_notepad,
            "notepad.close":self.close_notepad,
        }
    
    #fast intents 
    @property
    def fast_intents(self) -> Dict[str,List[str]]:
        return{
            "notepad.open": [
                "open notepad",
                "launch notepad",
                "start notepad",
                "open text editor",
                "create a note",
            ],
            "notepad.close":[
                "close notepad",
                "exit notepad",
                "quit notepad",
                "kill notepad",
            ],
        }

    #ai description
    @property
    def descriptions(self) -> Dict[str,str]:
        return{
            "notepad.open": "open the notepad text editor ",
            "notepad.close": "closes all open windows notepad windows",
        }
    

    #action logic
    def open_notepad(self,text:str="")-> bool:
        try:
            subprocess.Popen(["notepad.exe"])
            logger.info("Notepad launced successfully")
            return True
        except Exception as e:
            logger.error(f"failed to open notepad {e}")
            return False
    
    
    def close_notepad(self,text:str="")-> bool:
        return kill_process("notepad.exe")