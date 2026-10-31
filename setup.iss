; Η «συνταγή» του XrysaStudy-Setup.exe (Inno Setup). Την τρέχει το build.ps1, που δίνει και την έκδοση.
#ifndef MyAppVersion
  #define MyAppVersion "0.0"
#endif

[Setup]
; Σταθερό αναγνωριστικό: έτσι κάθε νέο setup αναβαθμίζει την ίδια εγκατάσταση αντί να φτιάχνει δεύτερη
AppId={{8F4B2C7A-3D1E-4B5A-9C6F-2A7E1D3B5C90}
AppName=XrysaStudy
AppVersion={#MyAppVersion}
AppPublisher=Giannis
AppPublisherURL=https://github.com/staaf83-svg/XrysaStudy
; Εγκατάσταση στον λογαριασμό του χρήστη: δεν ζητά δικαιώματα διαχειριστή, ούτε στις αναβαθμίσεις
DefaultDirName={localappdata}\Programs\XrysaStudy
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=XrysaStudy-Setup
SetupIconFile=xrysastudy.ico
UninstallDisplayIcon={app}\XrysaStudy.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
; shortcut: αγγλικά, γιατί το Inno Setup δεν φέρνει ελληνικά· η ανεπίσημη Greek.isl μπορεί να προστεθεί αργότερα
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; Σβήνει τα παλιά αρχεία του προγράμματος πριν μπουν τα νέα (οι ρυθμίσεις και τα έγγραφά σου δεν είναι εδώ)
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "dist\XrysaStudy\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\XrysaStudy"; Filename: "{app}\XrysaStudy.exe"
Name: "{autodesktop}\XrysaStudy"; Filename: "{app}\XrysaStudy.exe"; Tasks: desktopicon

[Run]
; Ανοίγει το πρόγραμμα στο τέλος (και μετά από αυτόματη αναβάθμιση)
Filename: "{app}\XrysaStudy.exe"; Description: "{cm:LaunchProgram,XrysaStudy}"; Flags: nowait postinstall
