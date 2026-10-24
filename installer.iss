#define AppName "PRIVACY68"
#ifndef AppVersion
  #define AppVersion "1.4.2"
#endif
#define AppPublisher "PRIVACY68"
#define AppExeName "PRIVACY68.exe"

[Setup]
AppId={{E13C0362-F02D-4F56-8D56-46D897B291A4}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\PRIVACY68
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}
SetupIconFile=assets\icon.ico
OutputDir=installer
OutputBaseFilename=PRIVACY68-Setup-v{#AppVersion}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
Uninstallable=yes
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "dist\PRIVACY68\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\PRIVACY68"; Filename: "{app}\{#AppExeName}"
Name: "{autoprograms}\PRIVACY68 Control Center"; Filename: "{app}\{#AppExeName}"; Parameters: "--dashboard"
Name: "{autodesktop}\PRIVACY68"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Open the PRIVACY68 Control Center"; Parameters: "--dashboard"; Flags: postinstall nowait skipifsilent unchecked
