# Tickora build script: env checks -> PyInstaller onedir -> Inno Setup (if installed).
param([string]$Version = "")

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Push-Location $Root
try {
    if (-not $Version) {
        $m = Select-String -Path "config.py" -Pattern 'APP_VERSION = "([^"]+)"' | Select-Object -First 1
        if ($m) { $Version = $m.Matches[0].Groups[1].Value } else { throw "Cannot read APP_VERSION from config.py" }
    }
    Write-Host "Target version: $Version"

    foreach ($p in @("settings.json", "user_data")) {
        if (Test-Path -LiteralPath $p) {
            throw "User data '$p' exists in the project root; move it away before building."
        }
    }
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "python not found" }
    python -c "import PyInstaller" 2>$null
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller missing; run: python -m pip install -r requirements-build.txt" }

    Write-Host "== PyInstaller onedir =="
    python -m PyInstaller --noconfirm --clean --distpath dist --workpath build scripts\TodoList.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }
    if (-not (Test-Path -LiteralPath "dist\TodoList\TodoList.exe")) { throw "dist\TodoList\TodoList.exe was not generated" }

    # Qt 6.11 compatibility fix: drop the ICU DLLs collected by PyInstaller and use
    # the Windows built-in %WINDIR%\System32\icuuc.dll. Otherwise the frozen app fails
    # to load Qt6Core.dll with "The specified procedure could not be found".
    foreach ($n in @("icuuc.dll", "icudt78.dll")) {
        $icu = Join-Path $Root "dist\TodoList\_internal\$n"
        if (Test-Path -LiteralPath $icu) {
            Remove-Item -LiteralPath $icu -Force
            Write-Host "Removed incompatible $n (using system ICU)"
        }
    }

    Write-Host "Runtime dir: $Root\dist\TodoList"

    $isccCandidates = @(
        "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    )
    $iscc = $isccCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $iscc) {
        Write-Host "Inno Setup compiler ISCC.exe not found; Setup.exe is NOT generated."
        Write-Host "Install it with: winget install JRSoftware.InnoSetup"
        Write-Host "Or download Inno Setup 6 from https://jrsoftware.org/isinfo.php"
        Write-Host "Then run: ISCC.exe /Qp /DMyAppVersion=$Version scripts\installer.iss"
    } else {
        Write-Host "== Inno Setup =="
        & $iscc /Qp "/DMyAppVersion=$Version" scripts\installer.iss
        if ($LASTEXITCODE -ne 0) { throw "Inno Setup compile failed" }
        Write-Host "Installer: $Root\dist_installer\TodoList_Setup_$Version.exe"
    }
} finally {
    Pop-Location
}
