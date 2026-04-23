# KASP Release v1.0 Analysis

## Scope

- Source/runtime baseline stays at `4.6.2`.
- GitHub release/build naming is aligned to `v1.0`.
- Legacy filename tokens such as `v4.6.2` and `v462` were removed from release-chain filenames.

## Streamlit Check

- No Streamlit version exists in this codebase.
- Repository search found no `streamlit` import and no `st.` usage.
- The web-facing implementation is FastAPI plus static HTML/JS under `kasp/api` and `kasp/web`.

## Naming Cleanup

- Kept one canonical release spec: `KASP_release_v1.0.spec`
- Kept one canonical release build script: `build_release_v1.0.bat`
- Kept one canonical local spec: `KASP_release_local.spec`
- Kept one generic local helper: `build_release.py`
- Added one local workspace batch helper: `build_release_local.bat`
- Removed stale historical variants: `KASP V4.6.spec`, `KASP_V461.spec`, `KASP_V61.spec`, `build_exe.bat`, `build_kasp.bat`

## Impact Analysis

- Runtime code does not import any of the removed historical spec or batch files, so desktop startup flow is unaffected.
- Build flow *is* affected by renaming, because PyInstaller and the copy-back step depended on specific filenames.
- To prevent rename-related breakage, release/build filenames are now driven from `release_metadata.py`.
- The version split is explicit:
  - `APP_VERSION = 4.6.2` is the software baseline shown inside the app.
  - `RELEASE_TAG = v1.0` is the packaging/release version used in release filenames.
- `KASP_release_v1.0.spec` and `KASP_release_local.spec` both import shared metadata, which removes duplicated hardcoded names.
- `build_release_v1.0.bat` now copies `release_metadata.py` into the isolated build workspace before running PyInstaller; without that step the renamed spec would fail to import metadata.
- Local build output naming is separated from release output naming, so workspace builds no longer carry stale source-version tags.

## Validation

- Unit/regression suite passes after the rename cleanup.
- Release build succeeds with the new release-chain names.
- `.gitignore` excludes build artifacts, caches, logs, and local editor noise so unnecessary files are not pushed.
