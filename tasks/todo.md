# Task List: General Camoufox Runtime Intelligence

IMPORTANT: When a task is fully completed and its verification commands pass, update this file and change that task checkbox from `- [ ]` to `- [x]` before finishing.

## Phase 1: Foundation Fixtures and Model Contract

- [x] Task 1: Add generic fixtures for modern dynamic page classes
  - Acceptance:
    - [x] Fixtures cover dense cards/listings, non-ARIA autocomplete, top-layer/intercepted clicks, nested scroll containers, and visual grids/keyboards.
    - [x] Tests assert the desired generic evidence/action behavior and fail without the new capability.
    - [x] Fixture names, text, selectors, and assertions do not mention public benchmark sites or mission IDs.
  - Verify:
    - [x] `uv run pytest -q tests/integration/test_interaction_events.py tests/integration/test_dom_selector_reliability.py`
    - [x] `uv run pytest -q tests/parity/test_search_extract_screenshot.py`
  - Dependencies: None
  - Files:
    - `tests/integration/test_interaction_events.py`
    - `tests/integration/test_dom_selector_reliability.py`
    - `tests/parity/test_search_extract_screenshot.py`

- [x] Task 2: Define bounded semantic model helpers
  - Acceptance:
    - [x] Evidence includes role/name/text/labels/owner/geometry/interactable state where available.
    - [x] Sensitive attributes and long text are redacted or bounded.
    - [x] Existing DOM selector behavior remains compatible with current tests.
  - Verify:
    - [x] `uv run pytest -q tests/unit/test_diagnostics.py tests/integration/test_dom_selector_reliability.py`
    - [x] `uv run pytest -q tests/parity/test_chrome_camoufox_dom_parity.py`
  - Dependencies: Task 1
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `tests/unit/test_diagnostics.py`
    - `tests/integration/test_dom_selector_reliability.py`
    - `tests/parity/test_chrome_camoufox_dom_parity.py`

## Checkpoint: Model Foundation

- [ ] Foundation fixtures fail for missing capabilities before implementation and pass after Task 2.
- [ ] Existing selectors, ordinals, disabled boundaries, and observable-only boundaries still pass.
- [ ] Diff review confirms no CDP, no BiDi, no public-site hardcoding.

## Phase 2: Dense Content Understanding

- [x] Task 3: Implement grouped card/list extraction
  - Acceptance:
    - [x] Generic dense-card fixture returns grouped units with title, primary link, price-like visible metadata, and actions.
    - [x] Output is compact, redacted, and bounded.
    - [x] Existing `find_elements`, `search_page`, and DOM parity tests continue to pass.
  - Verify:
    - [x] `uv run pytest -q tests/parity/test_search_extract_screenshot.py tests/integration/test_dom_selector_reliability.py`
    - [ ] Targeted run includes `ebay_product_filter` after implementation.
  - Dependencies: Tasks 1-2
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `tests/parity/test_search_extract_screenshot.py`
    - `tests/integration/test_dom_selector_reliability.py`

- [x] Task 4: Add grouped evidence to action relocalization diagnostics
  - Acceptance:
    - [x] Repeated-card fixture relocalizes the correct action using group context.
    - [x] Ambiguous repeated groups are rejected with ranked diagnostics.
    - [x] Diagnostics remain safe and size-bounded.
  - Verify:
    - [x] `uv run pytest -q tests/parity/test_stale_indexes.py tests/integration/test_dom_selector_reliability.py`
  - Dependencies: Task 3
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `tests/parity/test_stale_indexes.py`
    - `tests/integration/test_dom_selector_reliability.py`

## Checkpoint: Dense Pages

- [ ] Dense card/list fixtures pass.
- [ ] Existing search/extract/relocalization tests pass.
- [ ] `ebay_product_filter` targeted Camoufox run produces enough visible title/price evidence or passes.

## Phase 3: General Action Planner and Overlay Recovery

- [x] Task 5: Introduce conservative action planner diagnostics
  - Acceptance:
    - [x] Existing click/keyboard/form/autocomplete/frame-detach behavior is represented as action-plan steps.
    - [x] Last-click diagnostics include strategy, preconditions, attempted steps, and classified no-change reason.
    - [x] No behavior regresses for current integration and parity tests.
  - Verify:
    - [x] `uv run pytest -q tests/integration/test_interaction_events.py tests/parity/test_stale_indexes.py tests/parity/test_iframe_dom.py`
  - Dependencies: Tasks 1-2
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `tests/integration/test_interaction_events.py`
    - `tests/parity/test_stale_indexes.py`
    - `tests/parity/test_iframe_dom.py`

- [x] Task 6: Implement non-ARIA overlay/autocomplete selection
  - Acceptance:
    - [x] Generic non-ARIA autocomplete fixture selects the intended visible suggestion.
    - [x] Ambiguous or hidden suggestions are rejected with useful diagnostics.
    - [x] Existing ARIA listbox/menu option behavior continues to pass.
  - Verify:
    - [x] `uv run pytest -q tests/integration/test_interaction_events.py tests/parity/test_forms_dropdown_upload.py`
    - [ ] Targeted run includes `booking_destination_search` after implementation.
  - Dependencies: Task 5
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `tests/integration/test_interaction_events.py`
    - `tests/parity/test_forms_dropdown_upload.py`

- [ ] Task 7: Add hit-target, top-layer, and scroll-container recovery
  - Acceptance:
    - [ ] Intercepted/top-layer fixture classifies the blocker and avoids unsafe clicks.
    - [ ] Nested scroll-container fixture scrolls the correct container and clicks the intended target.
    - [ ] Safe coordinate click validates the hit target before use.
  - Verify:
    - [ ] `uv run pytest -q tests/integration/test_interaction_events.py tests/integration/test_dom_selector_reliability.py`
  - Dependencies: Task 5
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `tests/integration/test_interaction_events.py`
    - `tests/integration/test_dom_selector_reliability.py`

## Checkpoint: Action Recovery

- [ ] Existing click, keyboard, form, autocomplete, iframe, and scroll tests pass.
- [ ] `booking_destination_search` targeted Camoufox run passes or fails only as model/navigation with clear non-runtime diagnostics.
- [ ] No fallback force-clicks ambiguous, disabled, hidden, or observable-only nodes.

## Phase 4: Visual Grid and Virtual Keyboard Intelligence

- [ ] Task 8: Detect and expose compact grid state
  - Acceptance:
    - [ ] Generic grid fixture produces a compact grid summary with rows, columns, cell labels/text, and states.
    - [ ] Hidden or offscreen cells are not incorrectly reported as visible.
    - [ ] Output is bounded and does not read hidden app state or private data.
  - Verify:
    - [ ] `uv run pytest -q tests/integration/test_dom_selector_reliability.py tests/parity/test_chrome_camoufox_dom_parity.py`
  - Dependencies: Tasks 1-2
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `tests/integration/test_dom_selector_reliability.py`
    - `tests/parity/test_chrome_camoufox_dom_parity.py`

- [ ] Task 9: Detect virtual keyboard/button clusters
  - Acceptance:
    - [ ] Generic virtual-keyboard fixture exposes grouped rows and button states.
    - [ ] Keyboard-like clusters are bounded and do not flood normal pages.
    - [ ] Click/send_keys behavior remains unchanged unless the agent chooses visible controls.
  - Verify:
    - [ ] `uv run pytest -q tests/integration/test_interaction_events.py tests/integration/test_dom_selector_reliability.py`
    - [ ] Targeted run includes `wordle_solve_visible_feedback` after implementation.
  - Dependencies: Task 8
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `tests/integration/test_interaction_events.py`
    - `tests/integration/test_dom_selector_reliability.py`

## Checkpoint: Visual Interfaces

- [ ] Grid and virtual keyboard fixtures pass.
- [ ] Agent observations remain compact enough for benchmark runs.
- [ ] `wordle_solve_visible_feedback` targeted run improves or passes without using hidden state/site-specific logic.

## Phase 5: Benchmark Diagnostics and Final Gate

- [ ] Task 10: Improve runtime-vs-model benchmark classification
  - Acceptance:
    - [ ] Reports include bounded action-plan diagnostics when available.
    - [ ] Failure classes distinguish runtime/tooling, model/navigation, challenge, page availability, and verifier weakness.
    - [ ] Scrubbing prevents secrets, cookies, storage state, and large artifacts from leaking.
  - Verify:
    - [ ] `uv run pytest -q tests/parity/test_chrome_camoufox_dom_parity.py`
    - [ ] `uv run python scripts/real_world_kit.py --list-missions`
  - Dependencies: Tasks 3-9
  - Files:
    - `scripts/real_world_kit.py`
    - `tests/parity/test_chrome_camoufox_dom_parity.py`

- [ ] Task 11: Run targeted regression loop for remaining failures
  - Acceptance:
    - [ ] Targeted Camoufox report is generated under `artifacts/`.
    - [ ] `ebay_product_filter`, `booking_destination_search`, and `wordle_solve_visible_feedback` are classified with evidence.
    - [ ] Generated artifacts remain unstaged.
  - Verify:
    - [ ] `xvfb-run -a uv run python scripts/real_world_kit.py --runtime camoufox --mission ebay_product_filter --mission booking_destination_search --mission wordle_solve_visible_feedback --headless --pause-after-task 0 --report-path artifacts/real_world_kit/targeted-camoufox.json`
    - [ ] `git status --short`
  - Dependencies: Task 10
  - Files:
    - Generated files only under ignored `artifacts/real_world_kit/`

- [ ] Task 12: Run final validators and full 30-run benchmark
  - Acceptance:
    - [ ] Core validators pass.
    - [ ] Camoufox benchmark passes `15/15`.
    - [ ] Full matrix produces `30/30` rows.
    - [ ] Camoufox has zero `runtime/tooling` failures.
    - [ ] Reports are redacted and unstaged.
    - [ ] Diff review confirms no CDP, no BiDi, no public-site hardcoding, no generated artifacts, and no secrets.
  - Verify:
    - [ ] `uv run ruff check src tests scripts`
    - [ ] `uv run ruff format --check src tests scripts`
    - [ ] `uv run pyright`
    - [ ] `uv run pytest -q`
    - [ ] `xvfb-run -a uv run python scripts/real_world_kit.py --runtime camoufox --headless --pause-after-task 0 --report-path artifacts/real_world_kit/benchmark-camoufox/report.json`
    - [ ] `xvfb-run -a uv run python scripts/real_world_kit.py --runtime chrome --headless --pause-after-task 0 --report-path artifacts/real_world_kit/benchmark-chrome/report.json`
    - [ ] `git status --short`
    - [ ] `git diff`
  - Dependencies: Task 11
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `scripts/real_world_kit.py`
    - `tests/**`
    - Generated files under ignored `artifacts/`

## Final Checkpoint

- [ ] Human reviews plan and task list before implementation begins.
- [ ] Human resolves whether grouped content should be default observation or tool-first.
- [ ] If committing, run required git safety checks before staging.
