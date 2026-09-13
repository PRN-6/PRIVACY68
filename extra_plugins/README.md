# SANA Extra & Community Plugins

This directory contains standalone, optional plugins that are separated from SANA's default built-in core.

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

---

## 🚀 How to Install Them into SANA

You can install any of these plugins in **two ways**:

### Method 1: Via the SANA Control Center GUI (Recommended)
1. Open the **SANA Control Center** (right-click the tray icon $\to$ **Control Center & Settings**).
2. Go to the **🛠️ Create / Install Plugin** tab.
3. Click **"📁 Browse & Install Plugin File..."** and select `extra_plugins/whatsapp_plugin.py` or `extra_plugins/brave_plugin.py`.
4. It will automatically install into your `%APPDATA%\SANA\plugins\` folder and hot-reload immediately!

### Method 2: Manual Copy
Copy the `.py` file directly to your User AppData folder:
```powershell
Copy-Item "extra_plugins\whatsapp_plugin.py" -Destination "$env:APPDATA\SANA\plugins\"
```
Restart or open the Control Center, and SANA will automatically discover it.
