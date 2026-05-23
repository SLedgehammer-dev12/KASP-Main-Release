# KASP Main Release

KASP is a PyQt5-based compressor analysis and selection application with thermodynamic design, performance evaluation, and a lightweight FastAPI web surface.

## Current Release Baseline

- Application version: `1.6.1`
- GitHub release target: `v1.6.1`
- Desktop icon: compressor / gas turbine (`.ico` for Windows, `.icns` for macOS)
- English UI mode: set `app.language` to `"en"` in `kasp_config.json`
- Built-in update center: checks GitHub releases and lets the user choose download location

## Local Setup

```bash
python3 -m pip install --upgrade pip
pip install -r requirements.txt
python3 -m pytest -q
python3 main.py
```

## Build

### Windows
```powershell
.\build_release_v1.6.1.bat
```

### macOS
```bash
./build_release_v1.6.1.sh   # PyInstaller .app
./package_mac_dmg.sh         # create .dmg
```

For a workspace-only build without the release filename:

```powershell
.\build_release_local.bat    # Windows
```

Icons: `resources/icon.ico` (Windows), `resources/icon.icns` (macOS).<br>
Release spec files: `KASP_release_v1.6.1.spec` (Win), `KASP_release_v1.6.1_mac.spec` (mac).

## Notes

- Streamlit is not used in this codebase.
- The API/web path is implemented with FastAPI and static HTML/JS under `kasp/api` and `kasp/web`.
