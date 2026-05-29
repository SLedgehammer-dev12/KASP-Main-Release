# KASP Main Release

KASP is a PyQt5-based compressor analysis and selection application with thermodynamic design, performance evaluation, DWSIM EOS integration, advanced user management, and a lightweight FastAPI web surface.

## Current Release Baseline

- Application version: `2.0.0`
- GitHub release target: `v2.0.0`
- Desktop icon: compressor / gas turbine (`.ico` for Windows, `.icns` for macOS)
- English UI mode: set `app.language` to `"en"` in `kasp_config.json`
- Built-in update center: checks GitHub releases and lets the user choose download location

### New in v2.0.0
- **DWSIM EOS Integration** — 7th equation of state engine with Steam Tables, NRTL, PC-SAFT
- **Advanced User Management** — multi-user login, 4 roles, admin panel, forced password change
- **Engineering Mode** — calculation trace tree, EOS/Method shootout, debug logs, performance metrics
- **132 automated tests** (83% increase from v1.7.4)

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
.\build_release_v2.0.0.bat
```

### macOS
```bash
./build_release_v2.0.0.sh   # PyInstaller .app
./package_mac_dmg.sh         # create .dmg
```

For a workspace-only build without the release filename:

```powershell
.\build_release_local.bat    # Windows
```

## DWSIM Setup (Optional)

Place DWSIM DLL files in `kasp/core/libs/`:
- `DWSIM.Thermodynamics.StandaloneLibrary.dll` (required)
- `DWSIM.UnitOperations.dll` (optional, for future validation features)

On Windows, .NET Framework 4.x is pre-installed and DWSIM works out of the box.
On macOS, Mono or .NET SDK must be installed separately for DWSIM support.

Icons: `resources/icon.ico` (Windows), `resources/icon.icns` (macOS).<br>
Release spec files: `KASP_release_v2.0.0.spec` (Win), `KASP_release_v2.0.0_mac.spec` (mac).

## Notes

- Streamlit is not used in this codebase.
- The API/web path is implemented with FastAPI and static HTML/JS under `kasp/api` and `kasp/web`.
