; Tickora Windows 安装版 Inno Setup 脚本（需要 Inno Setup 6）。
; 由 scripts/build.ps1 传入 /DMyAppVersion=<版本>；未传时使用默认值 0.1.0。
; 数据目录 %LOCALAPPDATA%\ToDoList 由应用维护：安装、升级、卸载都不删除它。

#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif

#define MyAppName "Tickora"
#define MyAppAumid "Tickora"
#define MyAppRunValue "Tickora.Installed"

[Setup]
AppId=Xinluanfe1.Tickora
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=Xinluanfe1
DefaultDirName={localappdata}\Programs\ToDoList
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist_installer
OutputBaseFilename=TodoList_Setup_{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\TodoList.exe
AppMutex=Tickora.TodoList.SingleInstance
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务："; Flags: unchecked

[Files]
Source: "..\dist\TodoList\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\TodoList.exe"; AppUserModelID: "{#MyAppAumid}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\TodoList.exe"; Tasks: desktopicon; AppUserModelID: "{#MyAppAumid}"

[Run]
Filename: "{app}\TodoList.exe"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent unchecked

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', '{#MyAppRunValue}');
end;
