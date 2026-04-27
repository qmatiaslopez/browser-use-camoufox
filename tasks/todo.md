# Task List: General Chrome-Parity Camoufox Compatibility

IMPORTANT: When a task is fully completed and its Verify command passes, you must update this file and change that task checkbox from `- [ ]` to `- [x]` before finishing.

## Phase 1: Diagnostic Foundation

- [ ] Task 1: Add generic Chrome-vs-Camoufox fixture comparison
  - Acceptance:
    - [ ] Fixture contains no Wordle names, answer terms, or site-specific selectors.
    - [ ] Comparison reports visible text, attributes, interactive indexes, and non-actionable observable nodes.
    - [ ] Current Camoufox implementation shows at least one meaningful parity gap before generic adapter work.
  - Verify:
    - [ ] `uv run pytest -q tests/parity`
  - Dependencies: None
  - Files:
    - `tests/parity/test_chrome_camoufox_dom_parity.py`

- [ ] Task 2: Define generic DOM observation contract
  - Acceptance:
    - [ ] Observable non-actionable nodes are asserted separately from clickable nodes.
    - [ ] Generic state examples include ARIA state and bounded `data-*`.
    - [ ] Hidden/display-none nodes are excluded.
  - Verify:
    - [ ] `uv run pytest -q tests/parity/test_chrome_camoufox_dom_parity.py`
  - Dependencies: Task 1
  - Files:
    - `tests/parity/test_chrome_camoufox_dom_parity.py`

## Checkpoint: Diagnostic Foundation

- [ ] Human reviews generic contract.
- [ ] Parity gap is documented without Wordle.
- [ ] No runtime implementation has been changed.

## Phase 2: Generic Observation Slice

- [x] Task 3: Replace selector-specific extraction with a generic visible DOM walker
  - Acceptance:
    - [ ] No Wordle-specific or app-specific selector patterns remain.
    - [ ] Visible semantic non-interactive nodes appear in `dom_state.llm_representation()`.
    - [ ] Hidden nodes are omitted.
    - [ ] Prompt output is bounded.
    - [ ] Interactive selector ordinals remain stable.
  - Verify:
    - [ ] `uv run pytest -q tests/parity/test_chrome_camoufox_dom_parity.py`
    - [ ] `uv run pytest -q tests/integration/test_dom_selector_reliability.py`
  - Dependencies: Task 2
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `tests/integration/test_dom_selector_reliability.py`
    - `tests/parity/test_chrome_camoufox_dom_parity.py`

- [x] Task 4: Preserve actionability and safe interaction mapping
  - Acceptance:
    - [ ] Clickable controls still click by browser-use index.
    - [ ] Text inputs still accept `input` and printable `send_keys`.
    - [ ] Observable-only nodes return clear click diagnostics.
    - [ ] Disabled controls are represented as disabled.
  - Verify:
    - [ ] `uv run pytest -q tests/integration/test_dom_selector_reliability.py`
    - [ ] `uv run pytest -q tests/parity/test_search_extract_screenshot.py`
  - Dependencies: Task 3
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `tests/integration/test_dom_selector_reliability.py`

## Checkpoint: Generic Observation

- [ ] Generic fixture parity passes.
- [ ] Existing integration/parity tests pass.
- [ ] Diff review confirms no Wordle selectors or site-specific branches.

## Phase 3: Tool and Report Parity

- [x] Task 5: Align tool surfaces with generic observation
  - Acceptance:
    - [ ] `find_elements` includes standard observation attributes by default.
    - [ ] `find_elements` text output is normalized visible text.
    - [ ] `evaluate` returns valid JSON for structured values.
    - [ ] Search, screenshot, and PDF fallback behavior remain unchanged.
  - Verify:
    - [ ] `uv run pytest -q tests/parity/test_search_extract_screenshot.py`
  - Dependencies: Task 3
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `tests/parity/test_search_extract_screenshot.py`

- [x] Task 6: Add Chrome-vs-Camoufox parity matrix reporting
  - Acceptance:
    - [ ] Report includes runtime, fixture/page name, visible text parity, attribute parity, actionable count, observable-only count, and action result summary.
    - [ ] Report output is JSON and redacts sensitive values.
    - [ ] Report can be generated without committing artifacts.
  - Verify:
    - [ ] `uv run pytest -q tests/parity`
  - Dependencies: Tasks 3 and 5
  - Files:
    - `scripts/real_world_kit.py`
    - `tests/parity/test_chrome_camoufox_dom_parity.py`

## Checkpoint: Tool and Report Parity

- [ ] Parity tests pass.
- [ ] Generated matrix is human-readable.
- [ ] No generated artifacts are staged.

## Phase 4: Real-World Validation

- [x] Task 7: Run and compare real missions under Chrome and Camoufox
  - Acceptance:
    - [ ] Camoufox passes Wordle without manual intervention.
    - [ ] Camoufox passes SauceDemo without manual intervention.
    - [ ] Camoufox passes Wikipedia without manual intervention.
    - [ ] Chrome reports remain available as baseline comparison.
    - [ ] Remaining errors are classified as model, site, or runtime issues.
  - Verify:
    - [ ] `uv run python scripts/real_world_kit.py --runtime camoufox --mission wordle --mission saucedemo --mission wikipedia --pause-after-task 2`
    - [ ] `uv run python scripts/real_world_kit.py --runtime chrome --mission wordle --mission saucedemo --mission wikipedia --pause-after-task 2`
  - Dependencies: Task 6
  - Files:
    - No source changes expected unless validation reveals a bug.

- [ ] Task 8: Final validation and cleanup
  - Acceptance:
    - [ ] Lint, format, type check, and full tests pass.
    - [ ] Diff contains no CDP use, no Wordle-specific extraction selectors, and no secrets/artifacts.
    - [ ] `storage_state.json` and generated reports are not staged.
    - [ ] Plan/task files reflect completed work or remaining follow-ups.
  - Verify:
    - [ ] `uv run ruff check src tests scripts`
    - [ ] `uv run ruff format --check src tests scripts`
    - [ ] `uv run pyright`
    - [ ] `uv run pytest -q`
    - [ ] `git status --short`
    - [ ] `git diff`
  - Dependencies: Task 7
  - Files:
    - `src/browser_use_camoufox/session.py`
    - `tests/**`
    - `scripts/real_world_kit.py`
    - `SPEC.md`
    - `tasks/plan.md`
    - `tasks/todo.md`

## Final Checkpoint

- [ ] Human approves final behavior.
- [ ] Human decides whether to commit and push.
- [ ] If committing, run required git safety checks before staging.
