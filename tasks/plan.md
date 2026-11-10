# Implementation Plan: KASP Web Platform Transformation

## Overview
Transform KASP (Centrifugal Compressor Simulation & Selection Suite) into a 100% feature-complete, air-gapped capable, modular web application powered by FastAPI, pure ES6 modules, and Plotly.js, while maintaining full co-existence and backwards compatibility with the PyQt5 desktop application.

## Architecture Decisions
- **ADR-001 (Zero-Build Modular ES6 Web UI)**: Native ES modules with vendored Plotly.js, Lucide, and reactive store in `kasp/web/vendor/`. No node/npm dependency. Air-gapped and PyInstaller compatible.
- **ADR-002 (Service Layer Extraction)**: Extract business logic, validation, data preparation, and orchestration from `kasp/ui/` and `kasp/utils/workers.py` into `kasp/services/`, shared between Desktop PyQt5 and Web FastAPI.
- **ADR-003 (Interactive $k_{ij}$ Matrix Support)**: Add $N \times N$ binary interaction parameter visualization and override capability to the gas service and web UI.
- **ADR-004 (Headless First Rendering)**: Decouple `graphs.py`, `reporting.py`, and `i18n.py` from top-level PyQt5/Qt5Agg imports. Enable `io.BytesIO` in-memory streaming for PDF and SVG/PNG generation.
- **ADR-005 (Request-Scoped Multi-User Concurrency & Security)**: Session cookies + CSRF protection, SQLite-backed `AuthLockouts`, thread-isolated `run_id` cancel tracking, and thread-safe EOS solver pools.

## Task List

### Phase 1: Core Engine Concurrency & Headless Decoupling
- [ ] Task 1.1: Headless decoupling of `kasp/i18n.py` (extract Qt widget translator to `kasp/ui/i18n_qt.py`).
- [ ] Task 1.2: Headless decoupling of `kasp/utils/graphs.py` (lazy Qt imports, default headless `Agg` backend, `BytesIO` output).
- [ ] Task 1.3: Headless decoupling of `kasp/utils/reporting.py` (`io.BytesIO` PDF target support, pass `headless=True` to graphs).
- [ ] Task 1.4: Headless decoupling of `kasp/utils/logging_handler.py` (lazy Qt imports, thread-safe memory ring buffer for Web).
- [ ] Task 1.5: Concurrency fixes in `kasp/core/properties.py` (CoolProp thread-local AS pool, ThermoPack/DWSIM/NeqSim locks).
- [ ] Task 1.6: Calculation isolation & performance optimization in `kasp/core/thermo.py` (scoped `run_id`, disable uncertainty during intermediate consistency loops).
- [ ] Checkpoint 1: Run regression test suite (`pytest -q`) and verify 0 regressions.

### Phase 2: Business Logic Service Layer (`kasp/services/`)
- [ ] Task 2.1: Implement `kasp/services/gas_service.py` (19 gases, composition normalization, smart EOS/method recommendation, $N \times N$ $k_{ij}$ matrix builder/override).
- [ ] Task 2.2: Implement `kasp/services/validation_service.py` (pure Python validation for pressure, temperature, flow, speed).
- [ ] Task 2.3: Implement `kasp/services/design_input_service.py` (4 presets, live PR/dP calculation, guidance texts).
- [ ] Task 2.4: Implement `kasp/services/calculation_service.py` (2-stage design + turbine selection orchestration with API 617 1.04 margin correction).
- [ ] Task 2.5: Implement `kasp/services/performance_service.py` (ASME PTC-10 off-design test corrections and deviation evaluation).
- [ ] Task 2.6: Implement `kasp/services/chart_data_builder.py` (generate JSON numerical traces for all 9 charts + SVG compressor diagram).
- [ ] Checkpoint 2: Unit tests for `kasp/services/` verifying parity with existing desktop calculation workflows.

### Phase 3: Security, RBAC & FastAPI v1 Backend
- [ ] Task 3.1: SQLite migrations for `AuthLockouts` table and `CalculationHistory.user_id` ownership column.
- [ ] Task 3.2: Web Authentication & Session Management (HttpOnly Cookie, CSRF token, RBAC dependencies, brute-force lockout).
- [ ] Task 3.3: REST API Endpoints: Auth (`/api/v1/auth/*`) & User Management (`/api/v1/users/*`).
- [ ] Task 3.4: REST API Endpoints: Meta & Constants (`/api/v1/meta/*`), Gas & $k_{ij}$ (`/api/v1/thermo/*`).
- [ ] Task 3.5: REST API Endpoints: Calculations (`/api/v1/calculations/design`, `/api/v1/calculations/performance`).
- [ ] Task 3.6: REST API Endpoints: Equipment Catalog CRUD (`/api/v1/equipment/*`), Projects & History (`/api/v1/projects/*`).
- [ ] Task 3.7: REST API Endpoints: In-Memory Reports (`/api/v1/reports/pdf`, `/csv`) & Interactive Chart Data (`/api/v1/graphs/*`).
- [ ] Task 3.8: Asynchronous Job Manager & SSE Streaming (`/api/v1/jobs/*`) for 8-EOS / 6-Method shootouts with live cancellation.
- [ ] Checkpoint 3: Backend API integration tests covering auth, calculation, catalog, streaming reports, and shootout jobs.

### Phase 4: Modular Web UI (`kasp/web/`) — Shell, Design & $k_{ij}$
- [ ] Task 4.1: Download and vendor core offline libraries (`plotly.min.js`, `lucide.min.js`, etc.) into `kasp/web/vendor/`.
- [ ] Task 4.2: Setup CSS Design System (`tokens.css` with light/dark/engineering themes, `layout.css`, `components.css`).
- [ ] Task 4.3: Setup Client-side Core: `api/client.js`, `store/` (auth, project, ui, units), `i18n/locales.js` (TR/EN).
- [ ] Task 4.4: Implement Auth UI (Login Modal, Password Recovery, Force Password Change) and App Shell with 4 main tabs.
- [ ] Task 4.5: Implement Design Left Panel (Quick Presets, 19 Gas Table with live 100% check, 6 Steps, live PR/dP badges, contextual help).
- [ ] Task 4.6: Implement Interactive $N \times N$ $k_{ij}$ Matrix Modal & Override Editor.
- [ ] Task 4.7: Implement Design Results View (Key metric cards, turbine selection table, 6 detailed analysis tabs, PDF export).
- [ ] Checkpoint 4: End-to-end browser verification of Design calculation, $k_{ij}$ editing, and turbine selection.

### Phase 5: Interactive Charts, PTC-10, Shootout & Management
- [ ] Task 5.1: Implement Plotly.js charts for all 9 types (T-s, P-v, Mollier h-s, Sankey, k-Z, Stage Overview, Turbine Radar, Convergence, Cache).
- [ ] Task 5.2: Implement Reactive Compressor Architecture & Stage Flow SVG diagram.
- [ ] Task 5.3: Implement Performance (Off-Design / ASME PTC-10) tab with field test inputs, status badges, and deviation tables.
- [ ] Task 5.4: Implement Engineering Shootout tab with live SSE progress bar, stop button, and EOS/Method comparison matrices.
- [ ] Task 5.5: Implement Equipment Library Management modal (Turbine/Compressor search, filter, edit, add).
- [ ] Task 5.6: Implement Project History, Admin User Management, Preferences, and Real-time System Logs viewer.
- [ ] Checkpoint 5: Comprehensive system test, UI polish, security review, and documentation update.
