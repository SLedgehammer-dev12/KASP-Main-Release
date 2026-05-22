# KASP Main Release

KASP is a PyQt5-based compressor analysis and selection application with thermodynamic design, performance evaluation, and a lightweight FastAPI web surface.

## Current Release Baseline

- Application version: `1.5`
- GitHub release target: `v1.5`
- Desktop icon: natural gas turbine
- English UI mode: set `app.language` to `"en"` in `kasp_config.json`
- Built-in update center: checks GitHub releases and lets the user choose download location

## Local Setup

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m pytest -q
python main.py
```

## Build

```powershell
.\build_release_v1.5.bat
```

For a workspace-only build without the release filename, use:

```powershell
.\build_release_local.bat
```

The main desktop icon is expected at `resources/icon.ico`, and the canonical release spec is `KASP_release_v1.5.spec`.

## Notes

- Streamlit is not used in this codebase.
- The API/web path is implemented with FastAPI and static HTML/JS under `kasp/api` and `kasp/web`.
