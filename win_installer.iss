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
DefaultGroupName=sigmanight
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

[Code]
procedure CopyDirectoryTree(const SourceDir, DestDir: string);
var
  FindRec: TFindRec;
  SourcePath, DestPath: string;
begin
  if not ForceDirectories(DestDir) then
  begin
    MsgBox('Impossible de créer le dossier: ' + DestDir, mbError, MB_OK);
    Exit;
  end;
  if FindFirst(SourceDir + '\*', FindRec) then
  try
    repeat
      SourcePath := SourceDir + '\' + FindRec.Name;
      DestPath := DestDir + '\' + FindRec.Name;
      // Vérifie si c'est un répertoire
      if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
      begin
        // Évite les répertoires "." et ".."
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') then
        begin
          CopyDirectoryTree(SourcePath, DestPath);
        end;
      end
      else
      begin
        // Copie le fichier
        if not FileExists(DestPath) then
        begin
          if not FileCopy(SourcePath, DestPath, False) then
          begin
            MsgBox('Impossible de copier le fichier: ' + SourcePath + ' vers ' + DestPath, mbError, MB_OK);
            Exit;
          end;
        end;
      end;
    until not FindNext(FindRec);
  finally
    FindClose(FindRec);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if DirExists(expandConstant('{localappdata}\basilisk_llm')) then
    begin
      CopyDirectoryTree(expandConstant('{localappdata}\basilisk_llm'), expandConstant('{localappdata}\SigmaNight'));
      DelTree(expandConstant('{localappdata}\basilisk_llm'), True, True, True);
    end;
    if DirExists(expandConstant('{userappdata}\basilisk_llm')) then
    begin
      CopyDirectoryTree(expandConstant('{userappdata}\basilisk_llm'), expandConstant('{userappdata}\SigmaNight'));
      DelTree(expandConstant('{userappdata}\basilisk_llm'), True, True, True);
    end;
    if DirExists(expandConstant('{localappdata}\SigmaNight\basilisk')) then
    begin
      CopyDirectoryTree(expandConstant('{localappdata}\SigmaNight\basilisk'), expandConstant('{localappdata}\SigmaNight\basiliskLLM'));
      DelTree(expandConstant('{localappdata}\SigmaNight\basilisk'), True, True, True);
    end;
    if DirExists(expandConstant('{userappdata}\SigmaNight\basilisk')) then
    begin
      CopyDirectoryTree(expandConstant('{userappdata}\SigmaNight\basilisk'), expandConstant('{userappdata}\SigmaNight\basiliskLLM'));
      DelTree(expandConstant('{userappdata}\SigmaNight\basilisk'), True, True, True);
    end;
  end;
end;

[Run]
Filename: "{app}\basilisk.exe"; Parameters: "-n"; WorkingDir: "{app}"; Description: "{cm:LaunchProgram,{#SetupSetting("AppName")}}"; Flags: nowait postinstall skipifsilent unchecked
