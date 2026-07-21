; Dictate per-user installer — needs NO admin rights, shows NO UAC prompt.
; Build:  ISCC.exe packaging\installer.iss            (GPU variant)
;         ISCC.exe /DVariant=cpu packaging\installer.iss

#ifndef Variant
  #define Variant "gpu"
#endif
#define AppName "Dictate"
#define AppVersion "1.3.0"
#define AppExe "Dictate.exe"

[Setup]
AppId={{7D1C2E52-9B7A-4F1E-B0A3-D1CT8E000001}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Jaso
AppPublisherURL=https://gitea.taild045e.ts.net/jaso/transcribe
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputBaseFilename=Dictate-Setup-{#Variant}
OutputDir=Output
Compression=lzma2/max
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\assets\dictate.ico
InfoBeforeFile=quickstart.txt
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExe}

[Files]
Source: "..\build\dictate_launcher.dist\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs
Source: "quickstart.txt"; DestDir: "{app}"; DestName: "QuickStart.txt"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: startupicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "startupicon"; Description: "Start {#AppName} when I log in"; GroupDescription: "Startup:"

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName} now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; user data stays unless they delete it themselves; only clear the lock
Type: files; Name: "{localappdata}\Temp\transcribe-dictate.lock"
