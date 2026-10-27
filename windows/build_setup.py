"""Build the self-contained Windows CMD installer and its downloadable ZIP."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import zipfile


MARKER = '# FAULTLINE_SETUP_PAYLOAD'
HERE = Path(__file__).resolve().parent
README = '''Faultline: Einrichtung unter Windows

1. ZIP-Datei entpacken.
2. Setup-Faultline.cmd doppelt anklicken.
3. Nach der Installation deinen Meta-API-Key verdeckt eingeben.
4. Im automatisch geoeffneten Browser auf "Start hunt" klicken.

Der Installer nutzt dein vorhandenes Python (mindestens 3.10), laedt
Faultline von deinem GitHub-Repository und installiert die benoetigten
Pakete und den Test-Browser. Dafuer ist eine Internetverbindung erforderlich.

Danach startest du ueber "Faultline Live-Test" auf dem Desktop.
Installationsordner: %LOCALAPPDATA%\\Faultline
Dein Key wird nicht gespeichert und bleibt aus GitHub und Browser heraus.
Echte API-Aufrufe koennen dein Meta-Guthaben verbrauchen.
Zum Beenden das Konsolenfenster mit Strg+C stoppen.

Wenn Python fehlt, meldet der Installer dies mit dem offiziellen Downloadlink.
Der Installer wurde hier vorbereitet und geprueft; auf deinem PC wird er
erst durch deinen Doppelklick ausgefuehrt.
'''


def build(output: Path) -> tuple[Path, Path]:
    source = (HERE / 'Install-Faultline.ps1').read_text(encoding='utf-8')
    pin = re.search(r"^\$ReleaseCommit = '([0-9a-f]{40})'$", source, re.MULTILINE)
    if not pin:
        raise ValueError('Pin the released source commit before building the installer')
    if MARKER in source:
        raise ValueError('Installer source conflicts with the CMD payload marker')
    # The file path is passed through the environment, never interpolated into PowerShell code.
    # No elevation or execution-policy changes are requested.
    command = (
        '$source=[IO.File]::ReadAllText($env:FAULTLINE_INSTALLER_SELF);'
        "$parts=([regex]'(?m)^# FAULTLINE_SETUP_PAYLOAD\\r?$').Split($source,2);"
        "if($parts.Count -ne 2){throw 'Installer payload missing'};"
        '& ([ScriptBlock]::Create($parts[1]))'
    )
    header = '\n'.join([
        '@echo off',
        'setlocal DisableDelayedExpansion',
        'chcp 65001 >nul',
        'set "FAULTLINE_INSTALLER_SELF=%~f0"',
        'powershell.exe -NoLogo -NoProfile -Command "' + command + '"',
        'set "FAULTLINE_SETUP_EXIT=%ERRORLEVEL%"',
        'if not "%FAULTLINE_SETUP_EXIT%"=="0" (',
        '  echo.',
        '  echo Einrichtung nicht abgeschlossen. Bitte die Meldung oben beachten.',
        '  pause',
        ')',
        'exit /b %FAULTLINE_SETUP_EXIT%',
        MARKER,
        '',
    ])
    payload = (header + source.replace('\r\n', '\n')).replace('\n', '\r\n').encode('utf-8')
    if any(len(line) >= 8191 for line in payload.splitlines()[:13]):
        raise ValueError('CMD bootstrap exceeds the Windows command-line limit')
    output.mkdir(parents=True, exist_ok=True)
    cmd = output / 'Setup-Faultline.cmd'
    cmd.write_bytes(payload)
    archive = output / 'Faultline-Windows-Setup.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr(cmd.name, payload)
        package.writestr('LIESMICH.txt', README.replace('\n', '\r\n').encode('utf-8'))
    return cmd, archive


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    _, archive = build(args.output)
    print(archive.resolve())


if __name__ == '__main__':
    main()
