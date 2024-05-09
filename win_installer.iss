#ifndef AppArch
    #define AppArch "x64"
#endif
#define MyAppVersion GetVersionNumbersString('dist\basiliskLLM.exe')

[setup]
AppVersion={#MyAppVersion}
AppName=basiliskLLM
AppVerName={#SetupSetting("AppName")} {#SetupSetting("AppVersion")}
ArchitecturesAllowed={#AppArch}
ArchitecturesInstallIn64BitMode=x64 ia64
Output=yes
OutputDir=output_setup
OutputBaseFilename=setup_{#SetupSetting("AppName")}_{#SetupSetting("AppVersion")}_{#AppArch}
DefaultDirName={autopf}\basilisk_llm
DefaultGroupName=basiliskLLM
Compression=lzma2/ultra
SolidCompression=yes
VersionInfoProductName=basiliskLLM
AppReadmeFile=https://github.com/aaclause/basiliskLLM/
AppSupportURL=https://github.com/aaclause/basiliskLLM/issues
AppUpdatesURL=https://github.com/aaclause/basiliskLLM/releases
CloseApplications=yes
LicenseFile=LICENSE
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline dialog
RestartApplications=yes
ShowLanguageDialog=auto
Uninstallable=yes
UsePreviousAppDir=yes
UsePreviousLanguage=yes
UsePreviousPrivileges=yes
UsePreviousSetupType=yes
UsePreviousTasks=yes
ShowTasksTreeLines=no
[languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
name: "french"; MessagesFile: "compiler:Languages\French.isl"
[Files]
Source: "dist\*"; DestDir: "{app}"; Excludes: "\user_data"; Flags: recursesubdirs createallsubdirs sortfilesbyextension

[tasks]
Name: "DesktopIcon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
name: "StartupIcon"; Description: "{cm:AutoStartProgram,{#SetupSetting("AppName")}}"; GroupDescription: "{cm:AutoStartProgramGroupDescription}"; Flags: unchecked

[Icons]
Name: "{group}\{#SetupSetting("AppName")}"; Filename: "{app}\basiliskllm.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\{#SetupSetting("AppName")}"; Filename: "{app}\basiliskllm.exe"; WorkingDir: "{app}"; Tasks: DesktopIcon
Name: "{autostartup}\{#SetupSetting("AppName")}"; Filename: "{app}\basiliskllm.exe"; WorkingDir: "{app}"; Tasks: StartupIcon

[Run]
Filename: "{app}\basiliskllm.exe"; WorkingDir: "{app}"; Description: "{cm:LaunchProgram,{#SetupSetting("AppName")}}"; Flags: nowait postinstall skipifsilent unchecked
