# KASP Changelog

All notable changes to KASP (Kompresör Tasarım ve Performans Simülatörü).

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
