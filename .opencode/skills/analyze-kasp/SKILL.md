---
name: analyze-kasp
description: Deeply analyze the KASP project across all dimensions: security, architecture, code quality, testing, performance, error handling. Returns prioritized findings with file:line references. Use when the user asks to analyze, review, or audit the KASP codebase.
---

# Analyze KASP

Perform a comprehensive software engineering analysis of the KASP project at `/Users/macbook/Documents/Kodlama/KASP`.

## Analysis Dimensions

Run the following analyses in parallel. For each, return findings with file path, line numbers, severity (CRITICAL/HIGH/MEDIUM/LOW), and actionable description.

### 1. Security Analysis
- Read `kasp/security.py` — input validation, SQL injection protection, path traversal
- Read `kasp/utils/updater.py` — TLS enforcement, SHA256 hash verification, zip path safety
- Read `kasp/config_manager.py` — check for plaintext secrets in config
- Read `main.py` — eval/exec usage, path safety
- Check all network URLs use `https://`

### 2. Architecture Analysis
- Read EVERY source file (skip tests/) — map the dependency graph
- Identify circular imports or tight coupling
- Check layer separation: UI strings in business logic? Calculation logic in UI?
- Verify Facade pattern integrity (ThermoEngine → sub-systems)
- Check modul boundaries: 25+ UI modules — any overlapping concerns?
- Module-level mutable state risks

### 3. Code Quality Analysis
- PEP 8 violations: line length, blank lines, import order
- Duplication: unit conversion code, gas composition UI patterns
- Method complexity: >100 line methods, >3 level nesting, >5 parameters
- Dead code: unused imports, unreachable branches
- Type safety: missing type hints, dict key access without `.get()`
- String handling: hardcoded Turkish strings outside i18n.py
- Error-prone patterns: bare `except Exception: pass`, mutable defaults

### 4. Testing Analysis
- Coverage gaps: which modules have NO tests?
- Edge cases tested: division by zero, negative values, empty inputs, missing dict keys
- Test isolation and mock usage
- CI readiness: GitHub Actions config completeness
- pytest configuration quality

### 5. Performance Analysis
- CoolProp call count per calculation type
- Cache effectiveness: LRU hit ratio, composition-aware clearing
- Redundant property calculations
- Thread safety: lock contention, deadlock risks
- Startup time bottlenecks
- Matplotlib figure memory management

### 6. Error Handling Analysis
- Custom exception hierarchy usage
- Fallback chain completeness (CoolProp → PR/SRK → Ideal Gas)
- Global exception handler coverage
- Worker thread error boundaries
- UI error dialog consistency
- Logging completeness and level appropriateness

## Output Format

For each finding, produce a line with:
```
SEVERITY | File:line | Category | Finding description
```

Group findings by dimension. End with a summary table:

| Dimension | CRITICAL | HIGH | MEDIUM | LOW |
|-----------|----------|------|--------|-----|
| Security | - | - | - | - |
| Architecture | - | - | - | - |
| Code Quality | - | - | - | - |
| Testing | - | - | - | - |
| Performance | - | - | - | - |
| Error Handling | - | - | - | - |

Then provide a **Top 10 Priority Actions** list ordered by severity and impact.
