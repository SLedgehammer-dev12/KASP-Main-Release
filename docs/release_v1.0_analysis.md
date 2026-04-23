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

## v4.6.2 Repair

- The first `v1.0` release did not use the real `KASP V4.6` source tree as its runtime baseline.
- That mismatch removed the full EOS selector behavior from the delivered app and exposed a calculation path that could appear to hang.
- The release repository has now been resynchronized against the actual `KASP V4.6` application sources for `main.py`, the active `kasp/` runtime package, and the relevant legacy regression scripts.
- The release-specific packaging layer remains separate:
  - app/runtime version stays `4.6.2`
  - packaging/release tag stays `v1.0`

## Root Causes Found

- Wrong source baseline: the earlier release repo was built from `KASP Main`, not the working `KASP V4.6.2` desktop code.
- Wrong dependency pins: `requirements.txt` had `thermo>=0.4,<0.5`, but the real `KASP V4.6` working environment uses `thermo 0.6.0`, `chemicals 1.5.1`, `fluids 1.3.0`.
- Test drift: several `KASP Main` era tests were validating modules and workflows that do not belong to the `v4.6.2` runtime architecture.
- UI test blocking: the startup changelog dialog blocked headless test runs until explicit offscreen bypass logic was added.
- Logging lifecycle bug: the Qt log handler was retained by the root logger across window shutdown, causing cleanup noise and duplicate handlers.

## Corrective Actions

- Rebased the active release code on the actual `KASP V4.6` sources.
- Updated runtime version references from stale `4.2 DEEP` and `4.6.1` strings to the canonical `4.6.2` baseline where they still surfaced.
- Fixed `requirements.txt` to match the working dependency family required for full EOS support.
- Removed incompatible test files from the earlier wrong baseline and added targeted `v4.6.2` regressions for:
  - EOS selector population
  - design calculation returning without hanging
- Skipped the changelog dialog automatically in offscreen test runs.
- Refactored the Qt logging bridge so root logger cleanup does not retain a dead Qt-backed handler.

## Validation

- Unit/regression suite passes after the source repair and rename cleanup (`5 passed`).
- Release build succeeds with the corrected dependency set and the new release-chain names.
- `.gitignore` excludes build artifacts, caches, logs, and local editor noise so unnecessary files are not pushed.
