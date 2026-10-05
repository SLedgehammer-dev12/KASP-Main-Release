# KASP Repository Index

> **Auto-Generated Repository Map**
> **Commit**: `6ca6e9c` | **Version**: `v2.5.1` | **Date**: `2026-10-05`
> **Primary Stack**: Python 3.12/3.13, PyQt5, CoolProp, Thermo, NeqSim, FastAPI, SQLite3

---

## 1. Executive Architecture Summary

KASP (Kompresör Tasarım ve Performans Simülatörü) is an enterprise-grade centrifugal compressor thermodynamic and aerodynamic design/simulation application. It implements ASME PTC 10, ISO 5389, and API 617 standards.

```
                      +-----------------------------+
                      |         main.py             |
                      |   (PyQt5 Application Entry) |
                      +--------------+--------------+
                                     |
         +---------------------------+---------------------------+
         |                                                       |
         v                                                       v
+------------------+                                   +-------------------+
|     kasp.ui      | <----> [ Workers & Threads ] ---> |     kasp.core     |
| (Forms, Results, |                                   | (Thermodynamic &  |
|  Graphs, Themes) |                                   |  Aerodynamic Calc)|
+--------+---------+                                   +---------+---------+
         |                                                       |
         v                                                       v
+------------------+                                   +-------------------+
|    kasp.data     |                                   |  External Engines |
| (SQLite, Users,  |                                   | (CoolProp, Thermo,|
|  Audit, Projects)|                                   |  NeqSim, DWSIM)   |
+------------------+                                   +-------------------+
```

---

## 2. Directory Hierarchy & Metrics

| Directory / Package | Python Files | Lines of Code | Primary Role & Scope |
| :--- | :---: | :---: | :--- |
| `kasp/core/` | 24 | 9,894 | Pure thermodynamic calculations, EOS solvers, aerodynamic stages, ASME compliance |
| `kasp/ui/` | 31 | 10,797 | PyQt5 UI components, form inputs, dynamic results, dark/light themes, SVG generation |
| `kasp/utils/` | 8 | 3,837 | Matplotlib graph canvas, ReportLab PDF reports, background threads, auto-updater |
| `kasp/data/` | 2 | 847 | SQLite3 database schema, migration manager, user auth & PBKDF2 hashing |
| `kasp/api/` | 1 | 224 | FastAPI REST service for automated headless calculations |
| Root files (`main.py`, etc.) | 7 | 661 | Application bootstrap, release metadata, build configuration |
| Tests (`test_*.py`) | 50 | 8,663 | Full test coverage (407 test cases: 395 passed, 12 skipped) |
| **Total Codebase** | **123** | **34,923** | **Comprehensive industrial compressor design suite** |

---

## 3. Key Entry Points & Interfaces

1. **Desktop GUI (`main.py`)**:
   - Initializer: `main.py::main()`
   - Workflow: Theme loading -> Splash/Lockout check -> `LoginDialog` -> `KASPMainWindow` bootstrap.
   - Run: `python3 main.py` or `./KASP_Mac.command`
2. **Headless API Server (`kasp/api/server.py`)**:
   - Legacy/experimental; disabled unless `KASP_API_ENABLE=1` and `KASP_API_TOKEN` are set.
   - Endpoints: `/api/constants`, `/api/health`, `/api/calculate/design`, `/api/calculate/benchmark`.
   - Run: `KASP_API_ENABLE=1 KASP_API_TOKEN=... python3 -m kasp.api.server`
3. **Packaging Scripts**:
   - `build_release.py`: prints the canonical release command for the current version.
   - `package_mac_dmg.sh`: native macOS `.dmg` generator.
   - Spec files: `KASP_release_v2.5.1.spec` (Win), `KASP_release_v2.5.1_mac.spec` (mac), `KASP_release_local.spec`.
4. **Canonical Metadata (`release_metadata.py`)**:
   - Single-source-of-truth for `RELEASE_VERSION = "2.5.1"`, release artifact names, and update repo.
5. **Verification Scripts**: `verify_independent.py`, `verify_stability.py`, `verify_textbook.py`.

---

## 4. Subsystem Details & Key Modules

### A. Core Thermodynamics (`kasp/core/`)
- `properties.py`: Multi-backend thermodynamic property calculator with LRU cache, kij binary interaction matrices, and phase boundary heuristics.
- `thermo.py`: Unified facade (`ThermoEngine`) coordinating design loops, gas state transitions, and stage iterations.
- `aerodynamics.py`: Flow coefficient, head coefficient, Schultz polytropic analysis, work input, and mechanical loss calculations.
- `thermo_methods.py`: Explicit implementations of ASME PTC 10, Schultz, Huntington, BWR, Lee-Kesler, and Peng-Robinson.
- `thermo_design_orchestration.py`: Multi-stage compressor design sequence, convergence checking, intercooling, stage-by-stage calculations.
- `compliance.py`: API 617 8th Edition and ASME PTC 10 allowable deviation and limit checking.

### B. User Interface (`kasp/ui/`)
- `main_window.py`: Central coordinator connecting input forms, status bars, action menus, and calculation triggers.
- `design_left_panel_builders.py`: Dynamic input widgets for gas composition, inlet P/T, mass flow, and design constraints.
- `design_results_workflow.py`: Results visualization, stage summaries, thermodynamic Mollier diagrams.
- `theme_manager.py`: Modern dark/light stylesheet generation, WCAG contrast compliance.

### C. Utilities & Data (`kasp/utils/` & `kasp/data/`)
- `reporting.py`: PDF report generator (ReportLab) with executive summary, data tables, and embedded plots.
- `graphs.py`: Matplotlib figure canvas, Mollier h-s charts, P-h diagrams, compressor performance curves.
- `database.py`: SQLite connection manager, user table, projects table, audit log table, schema migrations.

---

## 5. Change Hotspots & High-Risk Areas

Based on recent commit activity (last 50 commits), the following files exhibit the highest churn:

1. **`kasp/ui/main_window.py`** (12 touches): UI signal routing. *Risk: Regressions in event loop or cross-tab synchronization.*
2. **`kasp/core/properties.py`** (11 touches): Core multi-backend property calculations. *Risk: Any modification affects all thermodynamic calculations; must preserve thread-safe caching and kij matrix integration.*
3. **`kasp/core/thermo.py`** (10 touches): Design iteration algorithms. *Risk: Energy balance closures and stage convergence.*
4. **`kasp/ui/design_left_panel_builders.py`** (10 touches): Input panel construction. *Risk: Layout/signal regressions across themes.*
5. **`kasp/core/aerodynamics.py`** (9 touches): Schultz polytropic methods. *Risk: ASME PTC 10 head and efficiency compliance.*
6. **`kasp/data/database.py`**: User security and project persistence. *Risk: Migration integrity and lockout handling.*

---

## 6. Token Savings Metric

- **Full Codebase Raw Context**: ~34,923 lines (~280,000 tokens).
- **Index Document Size**: ~1,500 tokens.
- **Context Reduction / Savings**: **>99.4% token economy** for orientation and module targeting.
