# KASP Deep Review

Date: 2026-04-24
Scope: thermodynamic formulas, unit conversions, release-note/update UX, UI/UX architecture

## Critical Findings

1. Hardcoded changelog blocks new releases from appearing in the built-in release notes flow.
   - Files:
     - `kasp/ui/dialogs.py:123`
     - `kasp/ui/dialogs.py:135`
     - `kasp/ui/main_window_startup.py:33`
     - `kasp/ui/main_window.py:187`
   - Problem:
     - The startup changelog dialog is a static HTML block for `V4.6`, `V4.5`, and `V4.4`.
     - The suppression key is also hardcoded as `ui.skip_changelog_v46`.
     - New GitHub releases are visible in the updater dialog, but not in the startup release-notes experience.
   - Impact:
     - Every new release requires manual code editing.
     - Users can miss release history even when a newer version is published.
   - Recommendation:
     - Replace the static changelog dialog with a release-note dialog backed by GitHub releases or a versioned local changelog file.
     - Use a dynamic dismissal key such as `ui.last_seen_release_tag`.

2. Molar-flow conversion can silently use methane molecular weight for non-methane mixtures.
   - Files:
     - `kasp/core/thermo_support.py:86`
     - `kasp/core/thermo_support.py:91`
     - `kasp/core/thermo.py:145`
     - `kasp/core/thermo.py:151`
   - Problem:
     - `kgmol/h` and `kmol/h` conversion falls back to `16.04` g/mol when MW inference fails.
   - Impact:
     - Any mixed gas, hydrogen-rich gas, nitrogen-rich gas, or CO2-rich gas can produce materially wrong mass flow.
     - That contaminates shaft power, heat-rate, fuel demand, and selection outputs.
   - Recommendation:
     - Remove methane fallback from production calculations.
     - Fail loudly when MW cannot be inferred.
     - Centralize mixture MW computation in one source of truth and add regression tests for mixed gases.

3. Thermodynamic property bridge exposes a placeholder speed of sound.
   - File:
     - `kasp/core/thermo.py:102`
   - Problem:
     - The legacy dictionary returned by `_get_thermo_properties()` contains `'a': 300.0`.
   - Impact:
     - Any downstream logic that assumes this is physical speed of sound can be wrong without any warning.
   - Recommendation:
     - Either calculate speed of sound from the EOS backend or remove the field until a correct implementation exists.
     - Add an explicit compatibility flag if legacy consumers still require the key.

4. EOS solver failure falls back to an ideal-gas model too easily for a high-stakes engineering workflow.
   - File:
     - `kasp/core/properties.py:87`
     - `kasp/core/properties.py:205`
   - Problem:
     - Any exception in PR, SRK, or CoolProp property calculation drops to a simplified ideal-gas fallback.
   - Impact:
     - Real-gas cases can produce plausible but wrong outputs instead of a visible engineering failure.
     - This is dangerous in compressor sizing and performance comparison.
   - Recommendation:
     - Distinguish recoverable library issues from invalid-state issues.
     - Default to surfacing a blocking error for design calculations unless the user explicitly opts into fallback mode.

## High Findings

5. Unit catalog and conversion logic are inconsistent.
   - Files:
     - `kasp/core/units.py:16`
     - `kasp/core/units.py:34`
     - `kasp/core/units.py:77`
     - `kasp/ui/validators.py:190`
   - Problem:
     - `convert_pressure()` supports `bar(a)`, `bar(g)`, `psia`, and `psig`, but these are missing from `UNITS['pressure']`.
     - Flow conversions handle `kgmol/h` and `kmol/h`, but they are absent from `UNITS['flow']`.
   - Impact:
     - UI combo boxes, validations, reports, and conversion code can drift apart.
   - Recommendation:
     - Move all supported unit definitions to a single typed registry and drive UI combos, validation, and conversion from that registry.

6. Pressure validation is physically ambiguous.
   - Files:
     - `kasp/core/units.py:115`
     - `kasp/ui/validators.py:193`
   - Problem:
     - `validate_pressure_value()` allows negative `psi` and `bar` values because they may be gauge.
     - The UI validator correctly distinguishes absolute and gauge units, but the core validator does not.
   - Impact:
     - Invalid negative absolute pressures can reach the solver depending on caller path.
   - Recommendation:
     - Stop treating bare `psi` and `bar` as possibly-gauge in core validation.
     - Require explicit absolute/gauge units across the app.

7. Result conversion silently returns the original value for unsupported quantity types.
   - Files:
     - `kasp/core/thermo_support.py:104`
     - `kasp/core/thermo.py:160`
     - `kasp/utils/reporting.py:220`
   - Problem:
     - `convert_result_value()` only handles temperature, pressure, power, head, and heat rate.
     - Reporting code also passes `heating_value` and `fuel_flow`.
     - Unsupported conversion requests return the original value without error.
   - Impact:
     - Reports can display numerically wrong units while looking valid.
   - Recommendation:
     - Raise `UnitConversionError` for unsupported quantity types.
     - Add explicit converters for heating value and fuel flow.

8. Thermodynamic methods mix convergence logic, fallback logic, and reporting history in large routines.
   - File:
     - `kasp/core/thermo_methods.py:19`
     - `kasp/core/thermo_methods.py:143`
     - `kasp/core/thermo_methods.py:285`
   - Problem:
     - Method implementations bundle state retrieval, numerical iteration, fallback selection, logging, and history assembly.
   - Impact:
     - Hard to reason about infinite-loop symptoms, numerical stability, and regression coverage.
   - Recommendation:
     - Split each method into:
       - input normalization
       - iterative solver
       - fallback policy
       - result packaging
     - Then add deterministic convergence tests around each solver.

## Medium Findings

9. Thermodynamic property models include coarse placeholders that should be isolated from design-critical outputs.
   - File:
     - `kasp/core/properties.py:202`
     - `kasp/core/properties.py:216`
   - Problem:
     - Thermo-EOS viscosity is fixed at `1.1e-5`.
     - Ideal fallback uses synthetic `Cp`, `Cv`, `Z`, and entropy relations.
   - Impact:
     - Acceptable for rough previews, not acceptable as an invisible production fallback in a design tool.
   - Recommendation:
     - Mark approximate properties explicitly in the returned state.
     - Prevent approximate transport/property values from feeding standards-based reports without warnings.

10. UI startup and main window orchestration remain too monolithic.
    - Files:
      - `kasp/ui/main_window.py:41`
      - `kasp/ui/main_window.py:91`
      - `kasp/ui/main_window.py:2007`
    - Problem:
      - `main_window.py` is still about 2357 lines and directly owns logging, update checks, calculations, reporting, dialogs, and library management.
    - Impact:
      - A small UI change can affect unrelated startup or calculation behavior.
      - Automated UI regression coverage is harder to build.
    - Recommendation:
      - Continue the ongoing split already started in `main_window_startup.py` and related helper modules.
      - Move updater, report actions, and design workflow logic into dedicated controllers.

11. Encoding issues still degrade maintainability and UX polish.
    - Files:
      - `kasp/core/units.py`
      - `kasp/core/properties.py`
      - `kasp/ui/dialogs.py`
      - `kasp/ui/main_window.py`
    - Problem:
      - Many comments and several UI strings contain mojibake.
    - Impact:
      - Harder code review, weaker professional appearance, increased risk of mismatched unit labels.
    - Recommendation:
      - Normalize source files to UTF-8.
      - Run a focused pass on all user-visible strings before broader refactoring.

12. Some UI labels and internal units appear mismatched.
    - File:
      - `kasp/ui/dialogs.py:57`
    - Problem:
      - Compressor editor labels min/max flow as `kg/h`, while returned keys are `min_flow_kgs` and `max_flow_kgs`.
   - Impact:
     - Potential library-data corruption and operator confusion.
   - Recommendation:
     - Standardize internal storage units and label them explicitly in the editor and database layer.

## Refactoring Order

1. Release-note flow
   - Replace hardcoded startup changelog with dynamic release-note source.
   - Add tests for “every new release appears in release notes”.

2. Unit system hardening
   - Build a single unit registry.
   - Remove ambiguous pressure units.
   - Make unsupported conversions fail loudly.

3. Thermodynamic calculation safety
   - Eliminate methane MW fallback.
   - Separate approximate fallback states from production states.
   - Add convergence and mixed-gas regression tests.

4. Numerical solver refactor
   - Decompose `thermo_methods.py`.
   - Add per-method test fixtures and iteration diagnostics.

5. UI architecture cleanup
   - Continue splitting `main_window.py` into controllers/workflows.
   - Clean encoding and labels after the structural split.

## Suggested Test Additions

- Mixed-gas molar-flow conversion for methane/CO2 and methane/nitrogen blends.
- Negative absolute pressure rejection for `bar(a)` and `psia`.
- Report generation tests that fail on unsupported quantity conversions.
- Release-note startup dialog test using multiple GitHub release payloads.
- Convergence regression tests for all EOS methods shown in the UI.
- Boundary tests for high pressure ratio and low-efficiency cases.
