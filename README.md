# KASP Main Release

KASP is a PyQt5-based compressor analysis and selection application with thermodynamic design, performance evaluation, DWSIM EOS integration, advanced user management, and a lightweight FastAPI web surface.

## Current Release Baseline

- Application version: `2.4.2`
- GitHub release target: `v2.4.2`
- Desktop icon: compressor / gas turbine (`.ico` for Windows, `.icns` for macOS)
- English UI mode: set `app.language` to `"en"` in `kasp_config.json`
- Built-in update center: checks GitHub releases and lets the user choose download location

### Highlights since v2.0.0
- **6 calculation methods** (average, endpoint, incremental, direct H-S, Huntington-RK45, Schultz 3-exp)
- **Thermodynamic audit fixes** — energy-balance marking, solver convergence reporting, fallback traceability
- **Offline password recovery** — security question + one-time recovery key, per-user lockout
- **Left-panel ergonomics** and theme-contrast improvements

## Local Setup

```bash
python3 -m pip install --upgrade pip
pip install -r requirements.txt
python3 -m pytest -q
python3 main.py
```

For reproducible environments, `requirements.lock.txt` pins the direct dependencies
to the versions validated by the test suite.

### API (optional)

The FastAPI surface (`kasp/api/server.py`) is disabled by default. To enable it:

```bash
export KASP_API_ENABLE=1
export KASP_API_TOKEN="<strong-random-token>"
python3 -m kasp.api.server
```

## Build

### Windows
```powershell
.\build_release_v2.4.2.bat
```

### macOS
```bash
./build_release_v2.4.2.sh      # PyInstaller .app
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
Release spec files: `KASP_release_v2.4.2.spec` (Win), `KASP_release_v2.4.2_mac.spec` (mac).

## Notes

- Streamlit is not used in this codebase.
- The API/web path is implemented with FastAPI and static HTML/JS under `kasp/api` and `kasp/web`.
