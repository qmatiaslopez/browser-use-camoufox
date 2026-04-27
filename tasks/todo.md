# Task List: Total Camoufox Runtime Robustness

IMPORTANT: When a task is fully completed and its verification commands pass, update this file and change that task checkbox from `- [ ]` to `- [x]` before finishing.

## Phase 1: Diagnostic Foundation

- [x] Task 1: Add generic failing fixtures for remaining failure classes
  - Acceptance:
    - [x] Local fixtures reproduce ambiguity/timeouts/detach patterns generically.
    - [x] Tests assert the desired behavior and fail before runtime fixes.
    - [x] Fixture names and selectors are generic and do not mention MDN, IMDb, eBay, Booking, or Wordle.
  - Verify:
    - [x] `uv run pytest -q tests/integration/test_interaction_events.py tests/parity/test_stale_indexes.py`
  - Dependencies: None
  - Files:
    - `tests/integration/test_interaction_events.py`
    - `tests/parity/test_stale_indexes.py`
    - `tests/integration/test_dom_selector_reliability.py`

- [x] Task 2: Add semantic target evidence to DOM nodes
  - Acceptance:
    - [x] Every actionable node has a bounded semantic evidence payload.
    - [x] Sensitive attributes remain omitted/redacted.
    - [x] Output remains bounded and existing observable/actionable representation is preserved.
  - Verify:
    - [x] `uv run pytest -q tests/integration/test_dom_selector_reliability.py`
    - [x] `uv run pytest -q tests/parity/test_search_extract_screenshot.py`
  - Dependencies: Task 1
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `tests/integration/test_dom_selector_reliability.py`
    - `tests/parity/test_search_extract_screenshot.py`

## Checkpoint: Evidence Foundation

- [ ] Focused tests for generic fixtures and semantic evidence pass.
- [ ] Diff review confirms no public-site hardcoding and no CDP.
- [ ] Human reviews failure-class fixtures before action fallback work begins.

## Phase 2: Ranked Relocalization

- [ ] Task 3: Replace exact-signature relocalization with scored candidate ranking
  - Acceptance:
    - [ ] Repeated candidates can be resolved when one candidate clearly matches the original semantic evidence.
    - [ ] Ambiguous candidates remain blocked with score diagnostics.
    - [ ] Disabled and observable-only candidates are never selected.
  - Verify:
    - [ ] `uv run pytest -q tests/parity/test_stale_indexes.py`
    - [ ] `uv run pytest -q tests/integration/test_dom_selector_reliability.py`
  - Dependencies: Task 2
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `tests/parity/test_stale_indexes.py`
    - `tests/integration/test_dom_selector_reliability.py`

- [ ] Task 4: Add candidate ranking diagnostics
  - Acceptance:
    - [ ] Ambiguous relocalization errors include top candidate scores and safe evidence.
    - [ ] Diagnostics omit sensitive values and remain size-bounded.
    - [ ] Benchmark reports preserve these diagnostics under runtime/tool errors.
  - Verify:
    - [ ] `uv run pytest -q tests/parity/test_stale_indexes.py tests/parity/test_chrome_camoufox_dom_parity.py`
  - Dependencies: Task 3
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `tests/parity/test_stale_indexes.py`
    - `tests/parity/test_chrome_camoufox_dom_parity.py`

## Checkpoint: Relocalization

- [ ] Repeated-result fixture passes.
- [ ] Existing stale-index and observable-only safety tests pass.
- [ ] Ambiguity diagnostics are actionable and redacted.

## Phase 3: Safe Click and Submit Recovery

- [ ] Task 5: Implement safe click fallback pipeline
  - Acceptance:
    - [ ] Timeout-covered generic fixture succeeds when one safe target is clear.
    - [ ] Fallback refuses disabled/observable-only/ambiguous targets.
    - [ ] Fallback diagnostics record attempted path and final result.
  - Verify:
    - [ ] `uv run pytest -q tests/integration/test_interaction_events.py tests/parity/test_stale_indexes.py`
  - Dependencies: Task 4
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `tests/integration/test_interaction_events.py`
    - `tests/parity/test_stale_indexes.py`

- [ ] Task 6: Add generic form/search submit fallback
  - Acceptance:
    - [ ] Generic search form fixture succeeds when the button click times out but form submit/Enter works.
    - [ ] Fallback requires a clear associated form/input and does not submit unrelated forms.
    - [ ] Diagnostics distinguish click fallback from form submit fallback.
  - Verify:
    - [ ] `uv run pytest -q tests/integration/test_interaction_events.py tests/integration/test_dom_selector_reliability.py`
  - Dependencies: Task 5
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `tests/integration/test_interaction_events.py`
    - `tests/integration/test_dom_selector_reliability.py`

## Checkpoint: Click/Search Recovery

- [ ] MDN-like generic fixture passes.
- [ ] Click fallback does not regress disabled/observable-only boundaries.
- [ ] Run affected benchmark task: `mdn_related_api_flow` under Camoufox.

## Phase 4: Autocomplete and Dynamic Frame Recovery

- [ ] Task 7: Add generic autocomplete/listbox option selection recovery
  - Acceptance:
    - [ ] Generic autocomplete fixture selects the intended visible option.
    - [ ] Ambiguous suggestions are rejected with ranked diagnostics.
    - [ ] Works for ARIA listbox/menu/option patterns without site-specific selectors.
  - Verify:
    - [ ] `uv run pytest -q tests/integration/test_interaction_events.py tests/parity/test_forms_dropdown_upload.py`
  - Dependencies: Task 6
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `tests/integration/test_interaction_events.py`
    - `tests/parity/test_forms_dropdown_upload.py`

- [ ] Task 8: Add frame-detach recapture and retry
  - Acceptance:
    - [ ] Generic detach fixture retries once and succeeds if the target reappears.
    - [ ] Retry is bounded and reports frame-detach recovery diagnostics.
    - [ ] If the target does not reappear, failure clearly says frame/target unavailable.
  - Verify:
    - [ ] `uv run pytest -q tests/parity/test_iframe_dom.py tests/parity/test_stale_indexes.py`
  - Dependencies: Task 7
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `tests/parity/test_iframe_dom.py`
    - `tests/parity/test_stale_indexes.py`

## Checkpoint: Autocomplete/Frame Recovery

- [ ] Booking-like generic fixture passes.
- [ ] Existing iframe and dropdown tests pass.
- [ ] Run affected benchmark task: `booking_destination_search` under Camoufox.

## Phase 5: Benchmark Hardening and Final Gate

- [ ] Task 9: Improve benchmark verifier/report classification
  - Acceptance:
    - [ ] Matrix report summarizes pass/fail, runtime/tooling errors, candidate diagnostics, fallback paths, and owner category.
    - [ ] Reports remain redacted and generated only under `artifacts/`.
    - [ ] Tests cover the 15 mission stack and matrix deltas.
  - Verify:
    - [ ] `uv run pytest -q tests/parity/test_chrome_camoufox_dom_parity.py`
    - [ ] `uv run python scripts/real_world_kit.py --list-missions`
  - Dependencies: Tasks 4-8
  - Files:
    - `scripts/real_world_kit.py`
    - `tests/parity/test_chrome_camoufox_dom_parity.py`

- [ ] Task 10: Run targeted real-site regression loop
  - Acceptance:
    - [ ] `mdn_related_api_flow`, `imdb_title_lookup`, `ebay_product_filter`, and `booking_destination_search` are re-run under Camoufox.
    - [ ] Any remaining failure is classified with runtime/model/site/verifier ownership.
    - [ ] Generated artifacts remain unstaged.
  - Verify:
    - [ ] `xvfb-run -a uv run python scripts/real_world_kit.py --runtime camoufox --mission mdn_related_api_flow --mission imdb_title_lookup --mission ebay_product_filter --mission booking_destination_search --headless --pause-after-task 0 --report-path artifacts/real_world_kit/targeted-camoufox/report.json`
    - [ ] `git status --short`
  - Dependencies: Task 9
  - Files:
    - Generated files only under ignored `artifacts/real_world_kit/`

- [ ] Task 11: Run full validation and 30-run benchmark
  - Acceptance:
    - [ ] Core validators pass.
    - [ ] Camoufox produces 15/15 mission rows and zero `runtime/tooling` failures.
    - [ ] Full benchmark produces 30/30 rows.
    - [ ] Reports are redacted and unstaged.
    - [ ] Diff review confirms no CDP, no public-site hardcoding, no generated artifacts, and no secrets.
  - Verify:
    - [ ] `uv run ruff check src tests scripts`
    - [ ] `uv run ruff format --check src tests scripts`
    - [ ] `uv run pyright`
    - [ ] `uv run pytest -q`
    - [ ] `xvfb-run -a uv run python scripts/real_world_kit.py --runtime camoufox --headless --pause-after-task 0 --report-path artifacts/real_world_kit/benchmark-camoufox/report.json`
    - [ ] `xvfb-run -a uv run python scripts/real_world_kit.py --runtime chrome --headless --pause-after-task 0 --report-path artifacts/real_world_kit/benchmark-chrome/report.json`
    - [ ] `git status --short`
    - [ ] `git diff`
  - Dependencies: Task 10
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `scripts/real_world_kit.py`
    - `tests/**`

## Final Checkpoint

- [ ] Human reviews benchmark matrix and approves/blocks merge readiness.
- [ ] If committing, run required git safety checks before staging.
- [ ] Any unresolved public-site flake is documented with owner category and reproduction evidence.
