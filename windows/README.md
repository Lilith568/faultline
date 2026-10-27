# Windows setup

`Install-Faultline.ps1` installs a pinned Faultline release into a separate
per-user directory, installs its Python dependencies and Playwright Chromium,
checks a local browser startup, and creates a desktop launcher. It uses an
existing Python 3.10+ installation. No administrator access is needed.

Build the downloadable double-click installer with Python:

```bash
python windows/build_setup.py --output dist/windows
```

Distribute `Faultline-Windows-Setup.zip`. The user extracts it and double-clicks
`Setup-Faultline.cmd`; the CMD contains the exact PowerShell source, uses no
execution-policy override and makes no persistent policy change. If the
organization blocks running such installers, it stops rather than changing
those protections.

After installation, `scripts/start_local_demo.py` asks for a missing Meta key
without echoing or saving it, starts a loopback-only server and opens the
composer demo. The user presses **Start hunt** to make model requests. Subsequent
starts use the **Faultline Live-Test** desktop shortcut.

Existing projects, `.env` files and unrelated launchers are preserved. The
installer source pin names the commit containing the launcher. Changing the
release requires updating that pin and rebuilding the package.

Validation: the Python launcher and browser landing page have automated tests;
the installer was inspected for PowerShell 5.1 quoting and Windows paths. A
Windows/PowerShell execution environment was not available during preparation,
so the complete installation still needs a Windows run.
