# Φτιάχνει το XrysaStudy.exe (PyInstaller) και το Output\XrysaStudy-Setup.exe (Inno Setup).
# Χρήση: άνοιξε PowerShell σε αυτόν τον φάκελο και γράψε  .\build.ps1
# "Continue": τα ενημερωτικά μηνύματα του PyInstaller δεν είναι σφάλματα· οι αποτυχίες ελέγχονται παρακάτω
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

$version = (Select-String -Path xrysastudy.py -Pattern '^VERSION = "(.+)"').Matches[0].Groups[1].Value
Write-Host "Έκδοση $version"

# 1. Το πρόγραμμα ως .exe (με όλα τα πακέτα μέσα, χωρίς να χρειάζεται Python)
python -m PyInstaller --noconfirm --clean --windowed --name XrysaStudy --icon xrysastudy.ico `
    --add-data "CHANGELOG.md;." --add-data "xrysastudy.ico;." --collect-submodules google.genai `
    --exclude-module torch --exclude-module llvmlite --exclude-module numba --exclude-module pyarrow `
    --exclude-module scipy --exclude-module pandas --exclude-module matplotlib --exclude-module sympy `
    --exclude-module numpy --exclude-module sounddevice --exclude-module IPython --exclude-module jedi `
    xrysastudy.py
# (τα exclude: μεγάλα πακέτα που υπάρχουν στον υπολογιστή από άλλα προγράμματα αλλά το XrysaStudy δεν χρειάζεται)
if ($LASTEXITCODE) { throw "Το PyInstaller απέτυχε" }

# 2. Ο αυτόματος έλεγχος τρέχει και μέσα στο ίδιο το .exe, για να πιάσουμε πακέτα που λείπουν
$test = Start-Process "dist\XrysaStudy\XrysaStudy.exe" -ArgumentList "--selftest" -Wait -PassThru
if ($test.ExitCode) { throw "Ο έλεγχος του .exe απέτυχε — δες το $env:TEMP\xrysastudy_selftest.log" }

# 3. Το πρόγραμμα εγκατάστασης
$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe") |
    Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Δεν βρέθηκε το Inno Setup" }
& $iscc "/DMyAppVersion=$version" setup.iss
if ($LASTEXITCODE) { throw "Το Inno Setup απέτυχε" }
Write-Host "Έτοιμο: Output\XrysaStudy-Setup.exe (έκδοση $version)"
