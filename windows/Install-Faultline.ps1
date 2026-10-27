# Windows PowerShell 5.1 compatible. The packaged CMD reads this exact source.
# This installer changes only a per-user Faultline directory and a desktop shortcut.
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ReleaseCommit = '1c8575caf33ea4360ea875366f5bd3b8533ea8c2'
$Repository = 'Lilith568/faultline'
$stage = $null
$previousProgress = $ProgressPreference
$previousTls = [Net.ServicePointManager]::SecurityProtocol
$installerMutex = $null
$mutexOwned = $false

function Invoke-PythonStep {
    param([string]$Python, [string[]]$Arguments, [string]$Step)
    Write-Host $Step
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Step fehlgeschlagen (Exitcode $LASTEXITCODE)."
    }
}

function Find-FaultlinePython {
    # Embedded double quotes are unreliable across Windows PowerShell 5.1's
    # legacy native-argument boundary. Python accepts these single-quoted keys.
    $probe = "import json,sys; print(json.dumps({'executable':sys.executable,'version':list(sys.version_info[:2])})); raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
    $candidates = @(
        @{ Name = 'py'; Prefix = @('-3.12') },
        @{ Name = 'py'; Prefix = @('-3.13') },
        @{ Name = 'py'; Prefix = @('-3.11') },
        @{ Name = 'py'; Prefix = @('-3') },
        @{ Name = 'python'; Prefix = @() },
        @{ Name = 'python3'; Prefix = @() }
    )
    foreach ($candidate in $candidates) {
        $command = Get-Command $candidate.Name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -eq $command) { continue }
        # Do not launch the Microsoft Store via an unconfigured execution alias.
        if ($command.Source -like '*\Microsoft\WindowsApps\*') { continue }
        try {
            $arguments = @($candidate.Prefix) + @('-I', '-c', $probe)
            $output = @(& $command.Source @arguments 2>$null)
            if ($LASTEXITCODE -ne 0) { continue }
            $info = ($output -join "`n") | ConvertFrom-Json
            if ($null -ne $info -and $info.version[0] -eq 3 -and $info.version[1] -ge 10 -and
                (Test-Path -LiteralPath $info.executable -PathType Leaf)) {
                return [string]$info.executable
            }
        }
        catch {
            # A launcher can exist even when that particular Python version does not.
            continue
        }
    }
    throw 'Python 3.10 oder neuer wurde nicht gefunden. Installiere Python von https://www.python.org/downloads/windows/ und starte diese Datei erneut.'
}

function Assert-FaultlineArchive {
    param([string]$Archive, [string]$ExpectedRoot)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($Archive)
    try {
        if ($zip.Entries.Count -gt 5000) { throw 'Das Archiv enthaelt unerwartet viele Dateien.' }
        $totalBytes = [long]0
        $files = New-Object 'System.Collections.Generic.HashSet[string]'
        foreach ($entry in $zip.Entries) {
            $name = $entry.FullName.Replace([char]92, [char]47)
            $segments = $name.Split('/')
            if ([IO.Path]::IsPathRooted($name) -or $name.Contains(':') -or $name.Contains([char]0) -or
                $segments -contains '..' -or $segments[0] -cne $ExpectedRoot -or
                (($entry.ExternalAttributes -shr 16) -band 0xF000) -eq 0xA000) {
                throw 'Das Archiv enthaelt einen ungueltigen Dateipfad.'
            }
            $totalBytes += $entry.Length
            if ($totalBytes -gt 100MB) { throw 'Das Archiv ist unerwartet gross.' }
            [void]$files.Add($name)
        }
        foreach ($required in @('pyproject.toml', 'faultline/server.py', 'scripts/start_local_demo.py')) {
            if (-not $files.Contains("$ExpectedRoot/$required")) {
                throw "Die benoetigte Projektdatei $required fehlt im Archiv."
            }
        }
    }
    finally {
        $zip.Dispose()
    }
}

function Write-FaultlineLauncher {
    param([string]$InstallRoot, [string]$Commit)
    $path = Join-Path $InstallRoot 'Start-Faultline.cmd'
    if ((Test-Path -LiteralPath $path) -and
        -not ([IO.File]::ReadAllText($path).Contains('REM Faultline managed launcher'))) {
        # A coincidentally named user file is not ours to overwrite.
        $path = Join-Path $InstallRoot ("Start-Faultline-" + $Commit.Substring(0, 8) + '.cmd')
        if ((Test-Path -LiteralPath $path) -and
            -not ([IO.File]::ReadAllText($path).Contains('REM Faultline managed launcher'))) {
            throw 'Eine vorhandene Startdatei wird nicht ueberschrieben. Bitte benenne die gleichnamige Datei um.'
        }
    }
    # Relative paths and disabled delayed expansion preserve spaces, percent signs,
    # exclamation marks and ampersands in the Windows account/install path.
    $lines = @(
        '@echo off',
        'REM Faultline managed launcher',
        'setlocal DisableDelayedExpansion',
        ('pushd "%~dp0versions\' + $Commit + '"'),
        'if errorlevel 1 goto :location_error',
        '".venv\Scripts\python.exe" "scripts\start_local_demo.py"',
        'set "FAULTLINE_EXIT=%ERRORLEVEL%"',
        'popd',
        'if not "%FAULTLINE_EXIT%"=="0" pause',
        'exit /b %FAULTLINE_EXIT%',
        ':location_error',
        'echo Faultline wurde nicht gefunden. Bitte den Installer erneut starten.',
        'pause',
        'exit /b 1'
    )
    [IO.File]::WriteAllText($path, ($lines -join "`r`n") + "`r`n", [Text.Encoding]::ASCII)
    return $path
}

try {
    if ($env:OS -ne 'Windows_NT') { throw 'Dieser Installer ist fuer Windows bestimmt.' }
    if ($ReleaseCommit -notmatch '^[0-9a-f]{40}$') { throw 'Der Installer enthaelt noch keine freigegebene Projektversion.' }
    if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) { throw 'Der lokale Windows-Anwendungsordner ist nicht verfuegbar.' }
    $installerMutex = [Threading.Mutex]::new($false, 'Local\Faultline-PerUser-Setup')
    try { $mutexOwned = $installerMutex.WaitOne(0) }
    catch [Threading.AbandonedMutexException] { $mutexOwned = $true }
    if (-not $mutexOwned) { throw 'Eine Faultline-Einrichtung laeuft bereits. Bitte warte auf dieses Fenster.' }

    $python = Find-FaultlinePython
    $installRoot = Join-Path $env:LOCALAPPDATA 'Faultline'
    $versionsRoot = Join-Path $installRoot 'versions'
    $versionRoot = Join-Path $versionsRoot $ReleaseCommit
    $sourceMarker = Join-Path $versionRoot '.faultline-source-commit'
    [void][IO.Directory]::CreateDirectory($versionsRoot)

    if (Test-Path -LiteralPath $versionRoot) {
        if (-not (Test-Path -LiteralPath $sourceMarker -PathType Leaf) -or
            [IO.File]::ReadAllText($sourceMarker).Trim() -cne $ReleaseCommit) {
            throw 'Ein vorhandener Ordner dieser Version gehoert nicht nachweislich zu diesem Installer und bleibt unveraendert.'
        }
        Write-Host 'Vorhandene Faultline-Version wird verwendet. Lokale Einstellungen bleiben erhalten.'
    }
    else {
        $stage = Join-Path $installRoot ('.setup-' + [Guid]::NewGuid().ToString('N'))
        [void][IO.Directory]::CreateDirectory($stage)
        $archive = Join-Path $stage 'faultline.zip'
        $extracted = Join-Path $stage 'unpacked'
        $archiveRoot = 'faultline-' + $ReleaseCommit
        $uri = "https://github.com/$Repository/archive/$ReleaseCommit.zip"
        $ProgressPreference = 'SilentlyContinue'
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        Write-Host 'Faultline wird von deinem GitHub-Repository heruntergeladen ...'
        Invoke-WebRequest -UseBasicParsing -Uri $uri -OutFile $archive
        Assert-FaultlineArchive -Archive $archive -ExpectedRoot $archiveRoot
        Expand-Archive -LiteralPath $archive -DestinationPath $extracted
        # Move before creating the venv: virtual environments must not be relocated afterwards.
        Move-Item -LiteralPath (Join-Path $extracted $archiveRoot) -Destination $versionRoot
        [IO.File]::WriteAllText($sourceMarker, $ReleaseCommit, [Text.Encoding]::ASCII)
    }

    $project = Join-Path $versionRoot 'pyproject.toml'
    $helper = Join-Path $versionRoot 'scripts\start_local_demo.py'
    if (-not (Test-Path -LiteralPath $project -PathType Leaf) -or
        -not (Test-Path -LiteralPath $helper -PathType Leaf)) {
        throw 'Die installierte Projektversion ist unvollstaendig. Vorhandene Dateien bleiben erhalten.'
    }
    $venv = Join-Path $versionRoot '.venv'
    $venvPython = Join-Path $venv 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        Invoke-PythonStep -Python $python -Arguments @('-m', 'venv', $venv) -Step 'Lokale Python-Umgebung wird eingerichtet ...'
    }
    Invoke-PythonStep -Python $venvPython -Arguments @('-m', 'pip', 'install', '--disable-pip-version-check', '--editable', $versionRoot) -Step 'Faultline und benoetigte Pakete werden installiert ...'
    Invoke-PythonStep -Python $venvPython -Arguments @('-m', 'playwright', 'install', 'chromium') -Step 'Test-Browser wird eingerichtet ...'
    $browserProbe = @'
import fastapi, httpx, uvicorn, faultline.server
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch()
    browser.close()
print('Lokaler Browser-Test erfolgreich.')
'@
    Invoke-PythonStep -Python $venvPython -Arguments @('-c', $browserProbe) -Step 'Installation wird lokal geprueft ...'

    $launcher = Write-FaultlineLauncher -InstallRoot $installRoot -Commit $ReleaseCommit
    try {
        $desktop = [Environment]::GetFolderPath('Desktop')
        if (-not [string]::IsNullOrWhiteSpace($desktop) -and (Test-Path -LiteralPath $desktop -PathType Container)) {
            $shell = New-Object -ComObject WScript.Shell
            $shortcutPath = Join-Path $desktop 'Faultline Live-Test.lnk'
            $shortcut = $shell.CreateShortcut($shortcutPath)
            if ((Test-Path -LiteralPath $shortcutPath) -and
                -not [string]::Equals($shortcut.TargetPath, $launcher, [StringComparison]::OrdinalIgnoreCase)) {
                $shortcutPath = Join-Path $desktop ('Faultline Live-Test-' + $ReleaseCommit.Substring(0, 8) + '.lnk')
                if (Test-Path -LiteralPath $shortcutPath) {
                    throw 'Ein gleichnamiger fremder Desktop-Link bleibt unveraendert.'
                }
                $shortcut = $shell.CreateShortcut($shortcutPath)
            }
            $shortcut.TargetPath = $launcher
            $shortcut.WorkingDirectory = $installRoot
            $shortcut.Description = 'Faultline mit privater Meta-Key-Eingabe lokal starten'
            $shortcut.Save()
        }
    }
    catch {
        Write-Warning "Der Desktop-Link konnte nicht erstellt werden. Die Startdatei liegt unter $launcher"
    }

    Write-Host ''
    Write-Host 'Faultline ist eingerichtet. Der lokale Live-Test wird jetzt gestartet.' -ForegroundColor Green
    Write-Host 'Deinen Meta-Key gibst du ausschliesslich im folgenden lokalen Fenster verdeckt ein.'
    Push-Location -LiteralPath $versionRoot
    try {
        Invoke-PythonStep -Python $venvPython -Arguments @($helper) -Step 'Faultline startet ...'
    }
    finally {
        Pop-Location
    }
}
catch {
    Write-Host ''
    Write-Host ('Einrichtung abgebrochen: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
finally {
    $ProgressPreference = $previousProgress
    [Net.ServicePointManager]::SecurityProtocol = $previousTls
    if ($null -ne $stage -and (Test-Path -LiteralPath $stage)) {
        Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
    }
    if ($mutexOwned) { $installerMutex.ReleaseMutex() }
    if ($null -ne $installerMutex) { $installerMutex.Dispose() }
}
