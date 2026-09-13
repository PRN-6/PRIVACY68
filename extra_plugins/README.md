# Privacy68 Extra & Community Plugins

This directory contains standalone, optional plugins that are separated from Privacy68's default built-in core.

---

## 📦 Available Extra Plugins

1. **`whatsapp_plugin.py`** (💬 WhatsApp Desktop)
   - Launch app (`"open whatsapp"`)
   - Clean tree termination (`"close whatsapp"`)
   - New conversation shortcut (`"new chat in whatsapp"`)

2. **`brave_plugin.py`** (🦁 Brave Browser)
   - Launch browser (`"open brave"`)
   - Close browser (`"close brave"`)
   - Tab controls (`"new tab in brave"`, `"close tab in brave"`, `"reopen tab in brave"`)

3. **`vscode_plugin.py`** (🧑‍💻 Visual Studio Code)
   - Launch editor (`"open vscode"`)
   - Close editor (`"close vscode"`)
   - Open integrated terminal (`"open terminal in vscode"`)
   - Quick-open files (`"find file called config.json"`)
   - Search disk for a file and open it (`"search for a file called main.py in vscode"`)

4. **`gesture_plugin.py`** (🖐️ Webcam Hand Gesture Control)
   - Wake / listen / mute with palm & fist gestures
   - Alt+Tab app switcher mode
   - Thumbs-up left/right navigation
   - PowerPoint slide control (1 finger = previous, 2 fingers = next)

5. **`ppt_plugin.py`** (📽️ PowerPoint Control)
   - Launch / close PowerPoint
   - Start / end slideshow

6. **`notepad_plugin.py`** (📝 Notepad)
   - Launch / close Notepad
   - Type text into the active window

---

## 🚀 How to Install Them into Privacy68

You can install any of these plugins in **two ways**:

### Method 1: Via the Privacy68 Control Center GUI (Recommended)
1. Open the **Privacy68 Control Center** (right-click the tray icon → **Control Center & Settings**).
2. Go to the **🛠️ Create / Install Plugin** tab.
3. Click **"📁 Browse & Install Plugin File..."** and select `extra_plugins/whatsapp_plugin.py` or `extra_plugins/brave_plugin.py`.
4. It will automatically install into your `%APPDATA%\PRIVACY68\plugins\` folder and hot-reload immediately!

### Method 2: Manual Copy
Copy the `.py` file directly to your User AppData folder:
```powershell
Copy-Item "extra_plugins\whatsapp_plugin.py" -Destination "$env:APPDATA\PRIVACY68\plugins\"
```
Restart or open the Control Center, and Privacy68 will automatically discover it.