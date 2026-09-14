; ─────────────────────────────────────────────────────────────────────────────
; PRIVACY68 Assistant - Inno Setup Installer Script
; Build Command: Open this file in Inno Setup Compiler and click Build → Compile
; Output: installer/PRIVACY68-Setup-v1.0.0.exe
; ─────────────────────────────────────────────────────────────────────────────

#define MyAppName "PRIVACY68"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "PRIVACY68 Team"
#define MyAppURL "https://github.com/PRN-6/PRIVACY68"
#define MyAppExeName "PRIVACY68.exe"
#define MyAppDescription "AI-Powered Local Voice Assistant for Windows"

[Setup]
; Basic metadata
AppId={{9A4B7C2D-3F8E-4A1B-9C6D-5E2F7A8B3C1D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
AppCopyright=Copyright (C) 2026 {#MyAppPublisher}

; Installation directory — default to Program Files
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Output setup exe location
OutputDir=installer
OutputBaseFilename=PRIVACY68-Setup-v{#MyAppVersion}

; Compression
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Appearance
WizardStyle=modern
WizardSizePercent=120
SetupIconFile=assets\icon.ico

; Privileges
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Minimum Windows version: Windows 10
MinVersion=10.0.17763

; Allow user to launch app after install
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} v{#MyAppVersion}

; ─────────────────────────────────────────────────────────────────────────────
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

; ─────────────────────────────────────────────────────────────────────────────
[Tasks]
; Optional: Create Desktop shortcut
Name: "desktopicon"; Description: "Create a &Desktop shortcut"; GroupDescription: "Additional shortcuts:"
; Optional: Launch on Windows startup
Name: "startup"; Description: "Launch &PRIVACY68 automatically on Windows startup"; GroupDescription: "Startup:"

; ─────────────────────────────────────────────────────────────────────────────
[Files]
; Copy the entire compiled dist/PRIVACY68 folder into the install directory
Source: "dist\PRIVACY68\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; ─────────────────────────────────────────────────────────────────────────────
[Icons]
; Start Menu shortcut
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Comment: "{#MyAppDescription}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

; Desktop shortcut (only if user selected the task)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Comment: "{#MyAppDescription}"; Tasks: desktopicon

; ─────────────────────────────────────────────────────────────────────────────
[Registry]
; Windows Startup registry entry (only if user selected the task)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: startup

; ─────────────────────────────────────────────────────────────────────────────
[Run]
; Launch PRIVACY68 after clicking Finish
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName} now"; Flags: nowait postinstall skipifsilent

; ─────────────────────────────────────────────────────────────────────────────
[UninstallRun]
; Kill PRIVACY68 process before uninstalling
Filename: "taskkill"; Parameters: "/F /IM ""{#MyAppExeName}"""; Flags: runhidden

; ─────────────────────────────────────────────────────────────────────────────
[Messages]
; Customize Wizard UI text
WelcomeLabel1=Welcome to {#MyAppName} Setup
WelcomeLabel2=This wizard will install {#MyAppName} v{#MyAppVersion} — an ultra-fast, 100%% private AI voice assistant for Windows.%n%nClick Next to continue.
FinishedHeadingLabel=Setup Complete — {#MyAppName} is Ready!
FinishedLabel={#MyAppName} has been installed on your PC.%n%nSay "Privacy68" to wake it up and speak your command.%n%nClick Finish to exit Setup.
