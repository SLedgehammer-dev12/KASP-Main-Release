# KASP Changelog

All notable changes to KASP (Kompresör Tasarım ve Performans Simülatörü).

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
