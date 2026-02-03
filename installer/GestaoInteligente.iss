#define AppName "Gestão Inteligente"
#define AppExeName "GestaoInteligente.exe"
#ifndef AppVersion
#define AppVersion "0.1.0"
#endif

[Setup]
AppId={{94F5E6ED-10CF-4E1E-9E83-3D7E06F1D5C2}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\GestaoInteligente
DefaultGroupName=Gestão Inteligente
OutputDir=..\dist_installer
OutputBaseFilename=GestaoInteligente-Setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
WizardStyle=modern

[Files]
Source: "..\dist\GestaoInteligente\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Executar {#AppName}"; Flags: nowait postinstall skipifsilent
