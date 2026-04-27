# Task List: Generic Camoufox Reliability Improvements

IMPORTANT: When a task is fully completed and its verification commands pass, update this file and change that task checkbox from `- [ ]` to `- [x]` before finishing.

## Phase 0: Fair Instrumentation

- [x] Task 1: Add benchmark diagnostics and failure classes
  - Acceptance:
    - [x] Reports include final URL, title, body excerpt/metrics, action names/counts, duration, URL transitions, runtime/tool errors, and verifier details.
    - [x] Failures are classified generically as model/navigation, runtime/tooling, page availability, challenge/interruption, verifier weakness, or unknown.
    - [x] Report redaction continues to remove sensitive-looking keys and values.
  - Verify:
    - [x] `uv run pytest -q tests/parity/test_chrome_camoufox_dom_parity.py`
    - [x] `uv run ruff check scripts tests/parity/test_chrome_camoufox_dom_parity.py`
    - [x] `uv run ruff format --check scripts tests/parity/test_chrome_camoufox_dom_parity.py`
  - Dependencies: None
  - Files:
    - `scripts/real_world_kit.py`
    - `tests/parity/test_chrome_camoufox_dom_parity.py`

- [x] Task 2: Add shared text, attribute, and selector metadata helpers
  - Acceptance:
    - [x] DOM observation, `search_page`, and `find_elements` use consistent visible text normalization.
    - [x] Attribute capture is bounded and skips or redacts sensitive-looking values.
    - [x] Selector metadata remains stable across ordinals, frames, and open shadow roots.
    - [x] Disabled and observable-only action boundaries remain intact.
  - Verify:
    - [x] `uv run pytest -q tests/integration/test_dom_selector_reliability.py`
    - [x] `uv run pytest -q tests/parity/test_search_extract_screenshot.py`
    - [x] `uv run pyright`
  - Dependencies: Task 1
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `tests/integration/test_dom_selector_reliability.py`
    - `tests/parity/test_search_extract_screenshot.py`

## Checkpoint: Instrumentation Foundation

- [ ] Focused validators for Tasks 1-2 pass.
- [ ] Reports contain comparable Chrome/Camoufox evidence without generated artifacts staged.
- [ ] Shared helper behavior is covered by tests before dense-page changes begin.

## Phase 1: Dense-Page DOM Prioritization

- [x] Task 3: Prioritize central semantic content under observation limits
  - Acceptance:
    - [x] `<main>`, `[role=main]`, articles, lists, grids, tables, and card-like groups are retained when output is bounded.
    - [x] Repeated sidebars, filters, and navigation cannot consume the full observation budget when central content exists.
    - [x] Grouped observable units expose useful visible text and safe attributes without becoming clickable unless actually interactive.
  - Verify:
    - [x] `uv run pytest -q tests/parity/test_chrome_camoufox_dom_parity.py`
    - [x] `uv run pytest -q tests/integration/test_dom_selector_reliability.py`
  - Dependencies: Task 2
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `tests/parity/test_chrome_camoufox_dom_parity.py`
    - `tests/integration/test_dom_selector_reliability.py`

## Checkpoint: Dense-Page Slice

- [ ] Dense generic fixture proves main content survives bounded output.
- [ ] Existing selector/actionability tests still pass.
- [ ] Diff review confirms no domain names or public-site selectors were added.

## Phase 2: Dynamic DOM Action Recovery

- [x] Task 4: Add safe one-shot action relocalization
  - Acceptance:
    - [x] Recovery recaptures DOM at most once per action attempt.
    - [x] Recovery refuses disabled, observable-only, or ambiguous relocalized targets.
    - [x] Failure messages explain whether relocalization was unavailable, ambiguous, or blocked by safety checks.
  - Verify:
    - [x] `uv run pytest -q tests/parity/test_stale_indexes.py`
    - [x] `uv run pytest -q tests/integration/test_dom_selector_reliability.py`
  - Dependencies: Task 2
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `tests/parity/test_stale_indexes.py`
    - `tests/integration/test_dom_selector_reliability.py`

- [x] Task 5: Add post-click change diagnostics
  - Acceptance:
    - [x] Click diagnostics include URL/title change, DOM count change, visible text change summary, and target attribute change when available.
    - [x] Diagnostics are bounded and redact sensitive-looking values.
    - [x] Successful clicks keep existing return behavior unless the public contract requires a diagnostic result.
  - Verify:
    - [x] `uv run pytest -q tests/integration/test_interaction_events.py`
    - [x] `uv run pytest -q tests/parity/test_stale_indexes.py`
  - Dependencies: Task 4
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `tests/integration/test_interaction_events.py`
    - `tests/parity/test_stale_indexes.py`

## Checkpoint: Dynamic Action Slice

- [ ] Stale/dynamic target tests pass.
- [ ] Safety checks still prevent disabled and observable-only actions.
- [ ] Diagnostics are useful without leaking sensitive values.

## Phase 3: Scroll and Viewport Targeting

- [ ] Task 6: Target nearest meaningful scroll container
  - Acceptance:
    - [ ] Page-level scroll behavior remains unchanged when no index is supplied.
    - [ ] Indexed scroll finds a nearby scrollable container and applies bounded movement there.
    - [ ] Nested scroll fixture verifies the intended container moves while unrelated containers do not.
  - Verify:
    - [ ] `uv run pytest -q tests/integration/test_basic_actions.py tests/integration/test_interaction_events.py`
  - Dependencies: Task 2
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `tests/integration/test_basic_actions.py`
    - `tests/integration/test_interaction_events.py`

- [ ] Task 7: Add continuation and no-op scroll diagnostics
  - Acceptance:
    - [ ] Observation can indicate below/right continuation without exceeding output limits.
    - [ ] No-op scroll diagnostics include current offsets, max offsets, target index, and likely blocker category.
    - [ ] Repeated no-op behavior is covered by a deterministic local fixture.
  - Verify:
    - [ ] `uv run pytest -q tests/integration/test_basic_actions.py tests/integration/test_dom_selector_reliability.py`
  - Dependencies: Task 6
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `tests/integration/test_basic_actions.py`
    - `tests/integration/test_dom_selector_reliability.py`

## Checkpoint: Scroll Slice

- [ ] Nested scroll and no-op diagnostics tests pass.
- [ ] Existing scroll event behavior is preserved.
- [ ] Observation output remains bounded.

## Phase 4: Keyboard and App Focus

- [ ] Task 8: Normalize keyboard input handling
  - Acceptance:
    - [ ] Printable text, special keys, key chords, and newline/Enter sequences are handled by explicit paths.
    - [ ] Existing printable-word and special-key behavior remains compatible.
    - [ ] Invalid or ambiguous key strings produce clear diagnostics.
  - Verify:
    - [ ] `uv run pytest -q tests/integration/test_dom_selector_reliability.py tests/integration/test_basic_actions.py`
  - Dependencies: Task 2
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `tests/integration/test_dom_selector_reliability.py`
    - `tests/integration/test_basic_actions.py`

- [ ] Task 9: Add generic focus preparation and active-element diagnostics
  - Acceptance:
    - [ ] Keyboard-only actions can focus a generic body/canvas/app-root target when no editable element is active.
    - [ ] Diagnostics include active element tag, role, id/class summary, and text/label excerpt before and after.
    - [ ] Focus preparation never uses domain-specific selectors.
  - Verify:
    - [ ] `uv run pytest -q tests/integration/test_dom_selector_reliability.py`
  - Dependencies: Task 8
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `tests/integration/test_dom_selector_reliability.py`

## Checkpoint: Keyboard Slice

- [ ] Keyboard fixtures pass.
- [ ] Active-element diagnostics are bounded and generic.
- [ ] Existing action tests do not regress.

## Phase 5: Tool Surface Refinements

- [ ] Task 10: Align `find_elements` and `search_page` evidence
  - Acceptance:
    - [ ] `find_elements` and `search_page` use normalized visible text consistently.
    - [ ] Tool outputs include useful safe attributes and element path/context.
    - [ ] Hidden text remains excluded from visible text results.
    - [ ] No-CDP tool boundary remains covered.
  - Verify:
    - [ ] `uv run pytest -q tests/parity/test_search_extract_screenshot.py tests/integration/test_tools_no_cdp.py`
  - Dependencies: Tasks 2 and 3
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `tests/parity/test_search_extract_screenshot.py`
    - `tests/integration/test_tools_no_cdp.py`

- [ ] Task 11: Decide and implement optional layout summary only if approved
  - Acceptance:
    - [ ] Human approval is recorded before adding a new public tool/action surface.
    - [ ] If implemented, output summarizes visible regions/cards/forms generically and remains bounded/redacted.
    - [ ] If deferred, no public API or tool schema changes are made.
  - Verify:
    - [ ] If implemented: targeted tests for the new surface.
    - [ ] If deferred: `uv run pytest -q tests/parity/test_search_extract_screenshot.py tests/integration/test_tools_no_cdp.py`
  - Dependencies: Task 10
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `tests/parity/` or `tests/integration/` if approved

## Checkpoint: Tool Surface Slice

- [ ] Existing tool parity tests pass.
- [ ] Any new public surface was approved before implementation.
- [ ] Tool output remains bounded and redacted.

## Phase 6: Final Validation and Benchmark Smoke

- [ ] Task 12: Run full validators and benchmark smoke comparison
  - Acceptance:
    - [ ] Lint, format check, pyright, and full pytest pass.
    - [ ] Diff contains no fake CDP, no site-specific runtime logic, no generated artifacts, and no sensitive data.
    - [ ] Benchmark smoke results are classified with the new diagnostics and kept out of staged changes.
    - [ ] `tasks/todo.md` reflects completed work and remaining follow-ups.
  - Verify:
    - [ ] `uv run ruff check src tests scripts`
    - [ ] `uv run ruff format --check src tests scripts`
    - [ ] `uv run pyright`
    - [ ] `uv run pytest -q`
    - [ ] Optional smoke: `xvfb-run -a uv run python scripts/real_world_kit.py --runtime camoufox --mission wordle --headless --pause-after-task 0`
    - [ ] Optional smoke: `xvfb-run -a uv run python scripts/real_world_kit.py --runtime chrome --mission wordle --headless --pause-after-task 0`
    - [ ] `git status --short`
    - [ ] `git diff`
  - Dependencies: Tasks 1-11
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `scripts/real_world_kit.py`
    - `tests/**`
    - `tasks/todo.md`

## Final Checkpoint

- [ ] Full validators pass.
- [ ] Human reviews final behavior and decides whether to commit.
- [ ] If committing, run required git safety checks before staging.
