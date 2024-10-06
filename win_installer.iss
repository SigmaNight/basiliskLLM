#ifndef AppArch
    #define AppArch "x64"
#endif

#ifndef MyAppVersion
    #define MyAppVersion GetVersionNumbersString('dist\basilisk.exe')
#endif

[setup]
AppVersion={#MyAppVersion}
AppName=basiliskLLM
AppPublisher=SigmaNight
AppVerName={#SetupSetting("AppName")} {#SetupSetting("AppVersion")}
ArchitecturesAllowed={#AppArch}compatible
ArchitecturesInstallIn64BitMode=x64compatible
Output=yes
OutputDir=output_setup
OutputBaseFilename=setup_{#SetupSetting("AppName")}_{#SetupSetting("AppVersion")}_{#AppArch}
DefaultDirName={autopf}\basilisk_llm
DefaultGroupName=SigmaNight
Compression=lzma2/ultra
SolidCompression=yes
VersionInfoProductName=basiliskLLM
AppReadmeFile=https://github.com/SigmaNight/basiliskLLM/
AppSupportURL=https://github.com/SigmaNight/basiliskLLM/issues
AppUpdatesURL=https://github.com/sigmanight/basiliskLLM/releases
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
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "ukrainian"; MessagesFile: "compiler:Languages\Ukrainian.isl"

[Files]
Source: "dist\*"; DestDir: "{app}"; Excludes: "\user_data"; Flags: recursesubdirs createallsubdirs sortfilesbyextension ignoreversion

[tasks]
Name: "DesktopIcon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
name: "StartupIcon"; Description: "{cm:AutoStartProgram,{#SetupSetting("AppName")}}"; GroupDescription: "{cm:AutoStartProgramGroupDescription}"; Flags: unchecked

[Icons]
Name: "{group}\{#SetupSetting("AppName")}"; Filename: "{app}\basilisk.exe"; Parameters: "-n"; WorkingDir: "{app}"; hotkey: "CTRL+ALT+SHIFT+A"
Name: "{autodesktop}\{#SetupSetting("AppName")}"; Filename: "{app}\basilisk.exe"; Parameters: "-n"; WorkingDir: "{app}"; Tasks: DesktopIcon
Name: "{autostartup}\{#SetupSetting("AppName")}"; Filename: "{app}\basilisk.exe"; Parameters: "-n -m"; WorkingDir: "{app}"; Tasks: StartupIcon; flags: runminimized

[CustomMessages]
CreateDirError=Unable to create directory: %1
CopyFileError=Unable to copy file from: %1 to: %2



[Code]
procedure CopyDirectoryTree(const SourceDir, DestDir: string);
var
  FindRec: TFindRec;
  SourcePath, DestPath: string;
begin
  if not ForceDirectories(DestDir) then
  begin
    MsgBox(FmtMessage(CustomMessage('CreateDirError'), [DestDir]), mbError, MB_OK);
    Exit;
  end;
  if FindFirst(SourceDir + '\*', FindRec) then
  try
    repeat
      SourcePath := SourceDir + '\' + FindRec.Name;
      DestPath := DestDir + '\' + FindRec.Name;
      if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
      begin
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') then
        begin
          CopyDirectoryTree(SourcePath, DestPath);
        end;
      end
      else
      begin
        if not FileExists(DestPath) then
        begin
          if not FileCopy(SourcePath, DestPath, False) then
          begin
            MsgBox(FmtMessage(CustomMessage('CopyFileError'), [SourcePath, DestPath]), mbError, MB_OK);
            Exit;
          end;
        end;
      end;
    until not FindNext(FindRec);
  finally
    FindClose(FindRec);
  end;
end;
procedure MigrateAndDeleteDir(SourceDir, DestDir: string);
begin
  if DirExists(SourceDir) then
  begin
    CopyDirectoryTree(SourceDir, DestDir);
    DelTree(SourceDir, True, True, True);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    MigrateAndDeleteDir(expandConstant('{localappdata}\basilisk_llm'), expandConstant('{localappdata}\SigmaNight'));
    MigrateAndDeleteDir(expandConstant('{userappdata}\basilisk_llm'), expandConstant('{userappdata}\SigmaNight'));
    MigrateAndDeleteDir(expandConstant('{localappdata}\SigmaNight\basilisk'), expandConstant('{localappdata}\SigmaNight\basiliskLLM'));
    MigrateAndDeleteDir(expandConstant('{userappdata}\SigmaNight\basilisk'), expandConstant('{userappdata}\SigmaNight\basiliskLLM'));
  end;
end;

[Run]
Filename: "{app}\basilisk.exe"; Parameters: "-n"; WorkingDir: "{app}"; Description: "{cm:LaunchProgram,{#SetupSetting("AppName")}}"; Flags: nowait postinstall skipifsilent unchecked
