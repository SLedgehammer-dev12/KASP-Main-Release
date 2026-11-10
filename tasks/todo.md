# KASP Web Platform Transformation — Task List

## Phase 1: Core Engine Concurrency & Headless Decoupling
- [x] **TASK-1.1**: Decouple `kasp/i18n.py` from top-level PyQt5 imports; create `kasp/ui/i18n_qt.py` for Qt widget translation.
- [x] **TASK-1.2**: Decouple `kasp/utils/graphs.py` from top-level PyQt5/Qt5Agg imports; default to `FigureCanvasAgg` when headless; support `io.BytesIO`.
- [x] **TASK-1.3**: Update `kasp/utils/reporting.py` to support `io.BytesIO` targets and ensure `headless=True` is passed to all graph calls.
- [x] **TASK-1.4**: Decouple `kasp/utils/logging_handler.py` from unconditional PyQt5 imports; add thread-safe ring buffer log handler for web.
- [x] **TASK-1.5**: Concurrency & thread-safety in `kasp/core/properties.py` (CoolProp thread-local AS cache, ThermoPack/DWSIM/NeqSim thread safety).
- [x] **TASK-1.6**: Calculation isolation in `kasp/core/thermo.py` (scoped `run_id`, disable uncertainty during intermediate consistency loops).
- [x] **CHECKPOINT-1**: Run `pytest -q` to verify zero regressions on existing 407 tests.

## Phase 2: Business Logic Service Layer (`kasp/services/`)
- [x] **TASK-2.1**: Implement `kasp/services/gas_service.py` (19 gases, presets, normalization, smart recommendations, $N \times N$ $k_{ij}$ matrix).
- [x] **TASK-2.2**: Implement `kasp/services/validation_service.py` (pure Python input validation).
- [x] **TASK-2.3**: Implement `kasp/services/design_input_service.py` (presets, live PR/dP calculations, contextual guidance).
- [x] **TASK-2.4**: Implement `kasp/services/calculation_service.py` (2-stage design + turbine selection with API 617 1.04 margin).
- [x] **TASK-2.5**: Implement `kasp/services/performance_service.py` (ASME PTC-10 off-design test evaluation and deviations).
- [x] **TASK-2.6**: Implement `kasp/services/chart_data_builder.py` (Plotly numerical data series generator for 9 charts + SVG diagram).
- [x] **CHECKPOINT-2**: Run service layer unit tests and verify parity with desktop UI.

## Phase 3: Security, RBAC & FastAPI v1 Backend
- [x] **TASK-3.1**: SQLite schema migration: `AuthLockouts` table and `user_id` ownership column in `CalculationHistory`.
- [x] **TASK-3.2**: Request-scoped authentication middleware (HttpOnly session cookie, CSRF token, RBAC dependencies).
- [x] **TASK-3.3**: Auth & User Management REST endpoints (`/api/v1/auth/*`, `/api/v1/users/*`).
- [x] **TASK-3.4**: Metadata, Constants & Gas / $k_{ij}$ REST endpoints (`/api/v1/meta/*`, `/api/v1/thermo/*`).
- [x] **TASK-3.5**: Calculation REST endpoints (`/api/v1/calculations/design`, `/api/v1/calculations/performance`).
- [x] **TASK-3.6**: Equipment Catalog CRUD & Project Management REST endpoints (`/api/v1/equipment/*`, `/api/v1/projects/*`).
- [x] **TASK-3.7**: In-Memory Streaming Reports & Interactive Chart Data endpoints (`/api/v1/reports/*`, `/api/v1/graphs/*`).
- [x] **TASK-3.8**: Asynchronous Shootout Job Manager & SSE Streaming (`/api/v1/jobs/*`).
- [x] **CHECKPOINT-3**: Run backend API test suite.

## Phase 4: Modular Web UI (`kasp/web/`) — Shell, Design & $k_{ij}$
- [x] **TASK-4.1**: Vendor core JS/CSS libraries (`plotly.min.js`, `lucide.min.js`, etc.) into `kasp/web/vendor/`.
- [x] **TASK-4.2**: Implement CSS Design System (`tokens.css` with light/dark/engineering themes, `layout.css`, `components.css`).
- [x] **TASK-4.3**: Implement client-side core (`client.js`, reactive stores, `locales.js`).
- [x] **TASK-4.4**: Implement Auth modals and 4-tab App Shell with header and status bar.
- [x] **TASK-4.5**: Implement Design Left Panel (presets, 19 gases, 6 steps, live PR/dP, smart recommendations).
- [x] **TASK-4.6**: Implement Interactive $N \times N$ $k_{ij}$ Matrix Modal with view & override.
- [x] **TASK-4.7**: Implement Design Results View (key cards, turbine selection, 6 detailed analysis tabs).
- [x] **CHECKPOINT-4**: Browser smoke test of design calculation and $k_{ij}$ matrix editor.

## Phase 5: Interactive Visualizations, PTC-10, Shootout & Management
- [x] **TASK-5.1**: Implement Plotly.js charts for all 9 types with zoom, pan, hover, and PNG/SVG export.
- [x] **TASK-5.2**: Implement reactive compressor architecture and stage flow SVG diagram.
- [x] **TASK-5.3**: Implement Performance & Verification (ASME PTC-10) tab.
- [x] **TASK-5.4**: Implement Engineering Shootout tab with live SSE progress bar and cancel support.
- [x] **TASK-5.5**: Implement Equipment Library management modal (Turbines & Compressors CRUD).
- [x] **TASK-5.6**: Implement Project History, Admin User Management, Preferences, and Real-time Logs viewer.
- [x] **CHECKPOINT-5**: Final comprehensive test suite, code review, and verification.
