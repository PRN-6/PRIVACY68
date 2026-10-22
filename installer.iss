; ─────────────────────────────────────────────────────────────────────────────
; PRIVACY68 Assistant - Inno Setup Installer Script
; Build Command: Open this file in Inno Setup Compiler and click Build → Compile
; Output: installer/PRIVACY68-Setup-v1.4.1.exe
; ─────────────────────────────────────────────────────────────────────────────

#define MyAppName "PRIVACY68"
#define MyAppVersion "1.4.1"
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
WelcomeLabel2=This wizard will install {#MyAppName} v{#MyAppVersion} — an ultra-fast, 100%% private AI voice assistant for Windows.%n%nNew in v1.4.1: App-Context Command Routing, Enhanced WhatsApp Automation, and Compound Command Planner.%n%nClick Next to continue.
FinishedHeadingLabel=Setup Complete — {#MyAppName} is Ready!
FinishedLabel={#MyAppName} has been installed on your PC.%n%nSay "Privacy68" to wake it up and speak your command.%n%nClick Finish to exit Setup.

; ─────────────────────────────────────────────────────────────────────────────
[Code]
; ─────────────────────────────────────────────────────────────────────────────
; The Control Center is rendered by pywebview, which needs the Microsoft Edge
; WebView2 Runtime. Most Windows 10/11 machines already have it, but LTSC,
; Enterprise, freshly imaged and debloated PCs often do not — and without it
; the Control Center opens as a blank window after a long pause. The installer
; therefore detects the runtime and installs the official Evergreen
; bootstrapper when it is missing.
; ─────────────────────────────────────────────────────────────────────────────
const
  WebView2ClientGuid = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  WebView2DownloadUrl = 'https://go.microsoft.com/fwlink/p/?LinkId=2124703';
  WebView2Bootstrapper = 'MicrosoftEdgeWebview2Setup.exe';

function HasWebView2Entry(RootKey: Integer; SubKey: String): Boolean;
var
  Version: String;
begin
  Result := False;
  if RegKeyExists(RootKey, SubKey) then
    Result := RegQueryStringValue(RootKey, SubKey, 'pv', Version);
end;

function IsWebView2Installed: Boolean;
var
  Base: String;
begin
  Base := 'Microsoft\EdgeUpdate\Clients\' + WebView2ClientGuid;
  Result :=
    HasWebView2Entry(HKLM, 'SOFTWARE\WOW6432Node\' + Base) or
    HasWebView2Entry(HKLM, 'SOFTWARE\' + Base) or
    HasWebView2Entry(HKCU, 'SOFTWARE\' + Base);
end;

procedure InstallWebView2;
var
  ResultCode: Integer;
  BootstrapperPath: String;
begin
  BootstrapperPath := ExpandConstant('{tmp}\') + WebView2Bootstrapper;

  if not DownloadTemporaryFile(WebView2DownloadUrl, BootstrapperPath) then
  begin
    Log('WebView2: could not download the Evergreen bootstrapper.');
    Log('WebView2: the Control Center will need the runtime installed manually.');
    Exit;
  end;

  { The bootstrapper installs per-machine when the user is an administrator
    and falls back to a per-user install otherwise. }
  if not Exec(BootstrapperPath, '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    Log('WebView2: the bootstrapper could not be launched.')
  else if ResultCode <> 0 then
    Log('WebView2: the bootstrapper exited with code ' + IntToStr(ResultCode) + '.')
  else
    Log('WebView2: the Evergreen runtime was installed successfully.');
end;

function InitializeSetup: Boolean;
begin
  Result := True;
  if IsWebView2Installed then
    Log('WebView2 Runtime detected — no runtime installation required.')
  else
    Log('WebView2 Runtime not detected — it will be installed after setup completes.');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if not IsWebView2Installed then
      InstallWebView2
    else
      Log('WebView2 Runtime detected — skipping runtime installation.');
  end;
end;
