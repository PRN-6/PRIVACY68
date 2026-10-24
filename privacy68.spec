# PyInstaller one-folder build for the PRIVACY68 Windows desktop application.
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

root = Path(SPECPATH).resolve()
datas = [
    (str(root / "assets"), "assets"),
    (str(root / "ui" / "dashboard"), "ui/dashboard"),
]
binaries = []
hiddenimports = []

for package in (
    "faster_whisper",
    "onnxruntime",
    "litellm",
    "webview",
    "pystray",
    "sounddevice",
    "pyttsx3",
    "ollama",
):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

for package in ("actions", "computer_use", "plugins", "server", "speech", "ui", "utils"):
    hiddenimports += collect_submodules(package)

# tiktoken discovers its encoding definitions by scanning the tiktoken_ext
# namespace package at runtime, which PyInstaller cannot infer from imports.
hiddenimports += collect_submodules("tiktoken_ext")

a = Analysis(
    [str(root / "app.py")],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tests"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PRIVACY68",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(root / "assets" / "icon.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="PRIVACY68",
)
