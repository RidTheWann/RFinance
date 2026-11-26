; SPDX-License-Identifier: GPL-3.0-only
; Copyright (C) 2026 RFinance Contributors
; See LICENSE for the full GNU General Public License version 3.

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

#define AppName "RFinance"
#define AppPublisher "RidTheWann"
#define AppExeName "RFinance.exe"

[Setup]
AppId={{7E10A6B6-80F7-4B7C-BB93-6D7E1D66C1B8}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://github.com/RidTheWann/RFinance
AppSupportURL=https://github.com/RidTheWann/RFinance/issues
AppUpdatesURL=https://github.com/RidTheWann/RFinance/releases
DefaultDirName={localappdata}\Programs\RFinance
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64
CloseApplications=yes
CloseApplicationsFilter={#AppExeName}
RestartApplications=no
UninstallDisplayIcon={app}\{#AppExeName}
LicenseFile=..\..\LICENSE
OutputDir=..\..\dist\installer
OutputBaseFilename=RFinance-Setup-{#AppVersion}-win-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
Uninstallable=yes
VersionInfoCompany={#AppPublisher}
VersionInfoDescription=Local-first investment research and simulated portfolio management
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}
VersionInfoVersion={#AppVersion}.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\..\dist\RFinance\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch RFinance"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent
