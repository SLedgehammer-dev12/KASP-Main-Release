# KASP Changelog

All notable changes to KASP (Kompresör Tasarım ve Performans Simülatörü).

---

## [v2.6.0] — 2026-10-05

### Fixed
- **AGA8-DC92 Critical Unit Fix** — pyaga8 is now given pressure in **kPa** (was MPa) and molar density is converted from **mol/L** (was treated as mol/cm³). This restores real-gas behaviour (Z, Cp/Cv, speed of sound) that was previously silently ideal-gas for all realistic pressures (~8% density error masked the bug).
- **Web UI Authentication** — `kasp/web/index.html` now sends `Authorization: Bearer <token>` to the protected `/api/calculate/*` endpoints, provides a persisted token field, and surfaces `401/403` as a clear "Token gerekli" state.
- **Release Build Metadata** — removed references to non-existent `build_release_v2.5.1.bat/.sh`; `build_release.py` now prints runnable `pyinstaller --clean <spec>` commands, with a drift test asserting referenced artifacts exist.
- **Updater SHA256 Binding** — release-body hashes are now bound to the correct asset (or fail closed) instead of being cross-assigned between assets.
- **Input-Safety Hardening** — polytropic-efficiency normalization, mole-fraction/percentage composition support, tolerant unit aliases, turbine-selection guards for zero/negative/non-finite power, and thread-safe catalog caching.
- **Resilient UI/Reporting** — design/performance result presenters, PDF reports, graphs and project serialization tolerate missing/None/NaN fields; updater downloads write a `.part` file and rename atomically after SHA256 verification.

### Added
- **Benchmark Solver Mode** — explicit diagnostic benchmark option distinct from the automatic smart chain.
- **Method Shootout Detail Panel** — selectable per-method detail with stage convergence, reference deltas and raw properties.
- **Stage-by-Stage PDF Breakdown** — optional multi-stage table in design reports.
- **Petrobras ccp Adapter** — resilient composition/unit normalization and KASP comparison utilities.
- **Repository Index** — `PROJECT_INDEX.md` / `PROJECT_INDEX.json` with verified metrics; agent skill manifests under `.agents/skills/`.

### Tests
- Full suite: **405 passed, 12 skipped, 0 failed**.

---

## [v2.5.1] — 2026-10-03

### Thermodynamic Safety & Numerical Accuracy
- **NeqSim Convergence Guard** — Enforced `thermo_health = "CRITICAL"` with `"neqsim_tp_flash_not_solved"` health reason when NeqSim flash solver reports `isSolved() == False`, preventing silent propagation of unconverged states.
- **INVALID Stage Aerodynamic Consistency** — Ensured both polytropic head (`head_kj_kg = 0.0`) and gas power are zeroed simultaneously in `staged_results` whenever energy balance fails ($\Delta h \le 0$).
- **Missing $k_{ij}$ Warning System** — Added detection of unparameterized pairs involving high-error polar and sour gas components ($CO_2, H_2S, H_2, H_2O$) in PR/SRK EOS, logging diagnostic warnings and recording `"missing_kij"` health tags.
- **Supercritical Fluid Phase Detection** — Added backend phase verification (`eos.phase in ('s', 'supercritical')`) and pseudo-critical property checking ($T > T_{c,pseudo}$, $P > P_{c,pseudo}$) in cubic EOS to preserve supercritical phase distinction.

### Code Quality & Architectural Consolidation
- **Single Source of Truth Normalization** — Consolidated chemical formula aliases (`CH4`, `C2H6`, `C3H8`, `IC4H10`, `NC4H10`, `C4H10`, etc.) into `constants.py:ALIAS_MAP` and unified `properties.py:_NORM_ALIASES`.
- **Cached Reverse Component Mapping** — Added `GasMixtureBuilder.REVERSE_THERMO_ID_MAP` to eliminate redundant dynamic dictionary allocations across 5 property solvers.
- **Magic Number Elimination** — Moved default mechanical efficiency (98%) and thermal efficiency (35%) into `EngineSettings` in `settings.py`.
- **Mechanical Loss Documentation** — Clarified ExxonMobil empirical formulation scope vs ASME PTC 10 internal design limitation in `calculate_mechanical_loss`.

---

## [v2.5.0] — 2026-10-02

### Major: Thermodynamic Core & Industrial Standards (API 617 / ASME PTC 10)
- **ASME PTC 10 & API 617 Compliance** — Fully standardized polytropic exponent evaluation, Schultz compressibility factor ($f_t$) integration, real-gas path integrals, and gas power balance verification. Centralized the API 617 4% driver margin (`API_617_DRIVER_MARGIN_PCT`).
- **Physical Efficiency Clamping** — Clamped physically impossible isentropic and polytropic efficiencies (>100% or negative) to `[0.0, 1.0]` with explicit engineering warning logs.
- **VLE Phase Envelope & Knockout Drum** — Enhanced condensation detection ($V_F < 1.0$) and minimum Gibbs free energy / fugacity phase stability checks.
- **Accurate Aerodynamic Margins** — Eliminated anomalous surge margin values (e.g. 3500%+) caused by incorrect reference flows, enforcing robust aerodynamic boundaries.
- **Inert Gas Fuel Consumption Fix** — Prevented false fuel consumption calculation for non-combustible gases (N₂, CO₂, etc.) when LHV <= 0.
- **Thread-Safe Solvers** — Guarded CoolProp `AbstractState` instances with concurrency locks to prevent race conditions during parallel evaluations.

### Security & Operational Hygiene
- **Database & Artifact Isolation** — Untracked `kasp_database.db` from repository, added `*.db` to `.gitignore`, and purged production databases from PyInstaller specs to ensure customer data and admin hashes never ship in release binaries.
- **Mandatory Password Reset Enforcement** — Fixed PBKDF2 verification for the initial admin credential, ensuring `must_change_password=1` triggers reliably.
- **SQLite WAL Mode** — Activated `PRAGMA busy_timeout = 5000` and `PRAGMA journal_mode = WAL` to prevent database locks.

### UI, Ergonomics & Quality of Life
- **Stale State Elimination** — Automatically clears residual results, summary cards, and stage tables upon calculation failure, performance error, or creating a new project (`clear_results_ui`).
- **UTF-8 Mojibake Elimination** — Cleaned up malformed Turkish character sequences in critical error and confirmation dialogs.
- **Keyboard Shortcuts** — Added `F5` / `Ctrl+R` shortcut for instant calculation triggers.

---

## [v2.4.2] — 2026-09-10

### Added & Improved
- **Offline Multi-Layer Password Recovery & Security Question** — Integrated Security Question & Answer mechanism with case-insensitive normalization and PBKDF2 hashing, 16-character Master Recovery Key (`KASP-XXXX-XXXX-XXXX`) for emergency administrator recovery, and "❓ Şifremi Unuttum" wizard in LoginDialog.
- **CLI Emergency Rescue Tool (`--reset-admin`)** — Added `python3 main.py --reset-admin` command to safely reset admin credentials to defaults, force password change on next login, generate a fresh recovery key, and clear lockout states without touching calculation history or equipment models.
- **In-App Security & Recovery Settings** — Added `SecuritySettingsDialog` under Tools menu for self-service question management and key generation.

---

## [v2.4.1] — 2026-09-09

### Fixed
- **Windows Password Lockout Bug** — Fixed perpetual lockout loop in `check_lockout` on Windows. Re-enabled password field immediately when timer hits zero, added live countdown in seconds and atomic UTF-8 state file persistence.
- **Engineering Trace Tree Stability** — Resolved `IndexError` in trace tree rendering across variable step lengths.
- **Method Recommendation Badge** — Resolved static analyzing placeholder; wired live signals to composition table and pressure edits.

### Added & Improved
- **13-inch MacBook Retina UI Optimization** — macOS Cocoa 72 DPI Retina scaling guard, 10-11pt base fonts, high-contrast text and active gas status badge.
- **Left Panel Ergonomics Overhaul** — 2-column stacked process conditions grid (45% vertical reduction), sticky action bar pinned to bottom, collapsible project notes and gas table, quick-preset chips (`Doğal Gaz`, `LNG`, `CO₂`, `H₂`), and live PR & ΔP badge.
- **3-Theme Header Contrast** — Verified WCAG 2.0 AAA contrast for Light (`#0F62FE`), Dark (`#3B82F6`), and Engineering (`#00B4D8`) themes, synchronized `app.setPalette` to eliminate macOS dark-mode bleed-through.
- **6-Method Shootout** — Expanded Engineering comparison to evaluate all 6 methods including Huntington-RK45 and Schultz 3-Exponent.

---

## [v2.0.1] — 2026-05-29

### Fixed
- **Thermopack PyInstaller Bundle** — `collect_data_files('thermopack')` ve `collect_submodules('thermopack')` eklendi. Binary olmadan "No such file or directory" hatası alınıyordu
- **Fallback log spam** — Rate-limit eklendi: her EOS için run başına 1 WARNING, sonrakiler DEBUG

---

## [v2.0.0] — 2026-05-29

### Major: DWSIM EOS Integration
- **DWSIM Standalone Thermodynamics Engine** — 7th EOS option with 16+ models
- Steam Tables (IAPWS-IF97) auto-detection when water fraction > 5%
- NRTL/UNIQUAC activity coefficient models for wet gas and polar mixtures
- Viscosity and thermal conductivity from DWSIM API
- Graceful fallback when pythonnet/DLL is missing — no crash

### Major: Advanced User Management
- Multi-user login with username + password (4 roles: Admin, Engineer, User, Viewer)
- Admin Panel — add/edit/delete users, reset passwords, toggle active/inactive
- Session management with login/logout, last-login tracking
- Role-based menu visibility: Log tab and Admin panel hidden for non-admins
- Forced password change after admin reset (`must_change_password` flag)
- `ChangePasswordDialog` — user self-service password change
- PBKDF2-SHA256 (600K iterations) secure password hashing

### Major: Engineering Mode (Admin Only)
- Toggle via Admin Panel checkbox (`updates.engineering_mode` config)
- **Calculation Trace Tree** — per-stage/iteration T, P, Z, k values in expandable tree
- **Performance Metrics** — cache hit rate, EOS call count, calculation time, success rate
- **Thermo Health Panel** — Z-factor anomalies, phase warnings (color-coded: green/yellow/red)
- **DEBUG log level** — 36 debug messages become visible in UI when engineering mode is active
- **Level-aware log filter** — hierarchical filtering (DEBUG > ITERATION > INFO > WARNING > ERROR)
- **EOS Shootout** — compare all 7 EOS engines on identical inputs (head diff %, timing)
- **Method Shootout** — compare all 4 sizing methods on identical inputs
- **Raw Property Comparison** — inlet MW, k, Z, Cp, Cv, density, phase per EOS side-by-side
- **Cache Performance graph** — now selectable from graph dropdown
- **CSV export** — trace data export button

### Fixed
- Method 4 solver bypass — user-selected State Solver now properly dispatched in Direct H-S
- BRENT root bracket safety — bisection fallback when bracket fails
- ThermoHandbook theme — SVG diagram dynamically adapts to Light/Dark/Engineering themes
- `filter_logs_by_level` — level-aware hierarchical filtering replaces substring matching
- `update_user` allowed set — `must_change_password` field now writable
- Test compatibility with Python 3.13 urllib ssl context parameter

### Added
- **Raw Property Comparison table** in Engineering Dashboard — EOS shootout now collects and displays inlet MW, k, Z, Cp, Cv, density, and phase for all 7 EOS backends
- `_extract_raw_properties()` helper in `kasp/core/engineering.py`
- DWSIM Bundle — `kasp/core/libs/` directory for DWSIM DLL files
- `sys._MEIPASS` search path in `_load_dwsim_dll()` for PyInstaller bundle
- `.spec` files include DWSIM DLL binaries + pythonnet hidden imports
- `test_dwsim_integration.py` — 7 tests (3 pass + 4 skip on macOS dev)
- `test_engineering_mode.py` — 18 tests (incl. 2 new graph cache performance tests)
- `test_engineering_shootout.py` — 7 tests
- `kasp/ui/diagram_svg.py` — theme-aware 3-layer SVG diagram generator
- Consolidated `CHANGELOG.md`

### Changed
- `_create_gas_object()` accepts `'dwsim'` as valid EOS method
- Test suite: **171 tests** (137% increase from 72), 0 regressions, 4 skipped (DWSIM)
- Release pipeline updated for v2.0.0

---

## [v1.7.4] — 2026-05-27

### Added
- **DWSIM Standalone Thermodynamics Engine** — 7th EOS option with 16+ models (PR, PRSV2, SRK, LKP, PC-SAFT, GERG-2008, Steam Tables, NRTL, UNIQUAC)
- **Steam Tables (IAPWS-IF97)** auto-detection when water fraction > 5%
- **Viscosity and thermal conductivity** properties from DWSIM
- **Advanced User Management** with multi-user support (4 roles: Admin, Engineer, User, Viewer)
- **Admin Panel** — add/edit/delete users, reset passwords, toggle active/inactive
- **Session management** with login/logout, last-login tracking
- **Permission control** — role-based menu visibility and feature access
- DWSIM DLL bundle support via `kasp/core/libs/` directory
- `test_dwsim_integration.py` — DWSIM EOS, SteamTables, viscosity tests (7 tests)
- `test_user_manager.py` — CRUD, auth, password management tests (21 tests)
- `test_security_session.py` — Session, PermissionManager, permission tests (17 tests)
- Consolidated `CHANGELOG.md`

### Fixed
- **Method 4 solver bypass** — user-selected State Solver now properly dispatched in Direct H-S method
- **BRENT root bracket safety** — bisection fallback when root bracket fails
- **ThermoHandbook theme** — now dynamically adapts to Light/Dark/Engineering themes
- **DWSIM UI disabled** — combo option disabled when pythonnet is missing (prevents invalid selection)
- **`last_login` field** — now correctly updated after successful authentication

### Changed
- `_create_gas_object()` now accepts `'dwsim'` as valid EOS method
- `_load_dwsim_dll()` search paths include `sys._MEIPASS` for PyInstaller bundle support
- `.spec` files updated for DWSIM + pythonnet bundling (both Windows and macOS)
- Release pipeline updated for v1.7.4

---

## [v1.7.1] — 2026-04

### Added
- Premium UI/UX themes: Light (Zinc White), Dark (Midnight Slate), Engineering (CAD Obsidian)
- WCAG AA contrast safeguards for labels and disabled elements
- Custom QComboBox dropdown styling
- macOS-style thin scrollbars
- Matplotlib graph theme synchronization

---

## [v1.7.0] — 2026-03

### Added
- Dynamic responsive UI with QSplitter panels
- 8 enhanced interactive graphs
- Theme switching (Light/Dark/Engineering)
- Language switching (TR/EN)
- 3-layer thermodynamic architecture (State Model → State Solver → Sizing Path)
- 4 sizing methods (Average Properties, Endpoint, Incremental, Direct H-S)
- 3 isentropic root solvers (AJ-NR, FD-NR, Brent)
- SINTEF thermopack EOS support
- Petrobras ccp EOS support
- Bilingual thermodynamics handbook dialog

---

## [v1.6.2] — 2026-02

### Fixed
- Case-folding duplicate index clash in CI
- CI pipeline configured for KASP directory

---

## [v1.6.1] — 2026-01

### Added
- macOS `.dmg` release packaging
- Windows `.exe` release packaging
- Responsive UI foundation
- Login authentication with PBKDF2-SHA256
- Brute-force lockout (4-tier escalating timeouts)

---

## [v1.6.0] — 2025-12

### Added
- CoolProp HEOS (GERG-2008) EOS support
- Peng-Robinson and SRK cubic EOS via Thermo library
- AGA8-DC92 (ISO 12213-2) natural gas standard
- Compressor design calculations
- Performance evaluation mode
- Turbine selection engine
- PDF reporting (ReportLab)
- Interactive graphs (Matplotlib)
- Gas composition editor
- Project save/load (JSON)

---

## [v1.5] — 2025-10

### Added
- Initial compressor performance calculations
- Basic UI with design tab
- Unit conversions

---

## [v1.4] — 2025-08

### Added
- Initial KASP prototype
- Basic thermodynamic property calculations
- Simple UI shell
