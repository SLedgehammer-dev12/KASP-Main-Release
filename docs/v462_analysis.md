# KASP v4.6.2 Analysis

## Baseline

- `KASP Main Release` was branched from `KASP Main` because it preserves the `v4.6.2` build path while keeping the newer expanded regression suite.
- The desktop runtime is PyQt5 based and starts from `main.py`.
- The project already includes a FastAPI + static web surface under `kasp/api/server.py` and `kasp/web/index.html`.

## Findings

- Historical `v4.6.2` build artifacts exist in the older `KASP V4.6/dist` folder, but several source files still exposed stale internal version strings such as `4.2 DEEP`.
- `main.py` expected `resources/icon.ico`, yet the repository had no icon asset or PyInstaller icon binding.
- English support was only partial: `app.language` existed in config and `error_handler.py` had bilingual entries, but the UI had no active localization pass.
- No Streamlit implementation exists in the codebase. Search results found neither `streamlit` imports nor `st.` usage.
- The web path is FastAPI served HTML/JS, not Streamlit.

## Release Changes

- Added a reusable UI localization helper in `kasp/i18n.py`.
- Standardized core version metadata to `4.6.2`.
- Added dependency and CI files for GitHub publishing.
- Wired a generated natural-gas-turbine icon into the `v4.6.2` build spec and build script.
