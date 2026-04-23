# KASP Main Release

KASP is a PyQt5-based compressor analysis and selection application with thermodynamic design, performance evaluation, and a lightweight FastAPI web surface.

## Current Release Baseline

- Source baseline: `v4.6.2`
- GitHub release target: `v1.0`
- Desktop icon: natural gas turbine
- English UI mode: set `app.language` to `"en"` in `kasp_config.json`

## Local Setup

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m pytest -q
python main.py
```

## Build

```powershell
pyinstaller --clean KASP_V462.spec
```

The main desktop icon is expected at `resources/icon.ico`.

## Notes

- Streamlit is not used in this codebase.
- The API/web path is implemented with FastAPI and static HTML/JS under `kasp/api` and `kasp/web`.
