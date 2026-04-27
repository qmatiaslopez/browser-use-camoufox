# Implementation Plan: General Chrome-Parity Camoufox Compatibility

## Overview

Replace the current selector-oriented Camoufox DOM extraction with a generic Playwright/Juggler-backed compatibility path that gives `browser-use` practical Chrome parity for observation and actions without CDP, fake CDP, or site-specific selectors. The plan is vertical: each task adds one complete observable/actionable user path with regression coverage and verification before moving to the next.

## Current State

- Generic Chrome-vs-Camoufox fixture parity, DOM observation contracts, generic visible DOM walking, actionability boundaries, tool parity, and parity matrix reporting are implemented and verified.
- Camoufox real-world validation passed Wordle, SauceDemo, and Wikipedia without manual intervention under `xvfb-run`.
- Chrome baseline reports remain available; observed Chrome mission failures were classified as model/agent step-budget or action-choice issues rather than Camoufox runtime gaps.
- Final validation passed: lint, format check, pyright, full pytest suite, and build.
- Generated artifacts remain outside staged changes.

## Dependency Graph

```text
SPEC.md boundaries
    │
    ├── Generic fixture contracts
    │       │
    │       ├── Chrome baseline capture
    │       │       │
    │       │       └── Camoufox parity assertions
    │       │               │
    │       │               └── Generic DOM observation adapter
    │       │                       │
    │       │                       ├── selector target mapping
    │       │                       │       │
    │       │                       │       └── click/type/scroll/dropdown actions
    │       │                       │
    │       │                       └── tool surfaces
    │       │                               ├── find_elements
    │       │                               └── evaluate/search/screenshot/pdf
    │       │
    │       └── Regression fixtures
    │
    └── Real-world kit
            │
            ├── Chrome comparison reports
            └── Camoufox mission validation
```

Implementation order follows this graph: fixture contract and diagnostics first, then generic DOM adapter, then action/tool parity, then real-world validation.

## Architecture Decisions

- **No CDP in Camoufox:** Camoufox must continue using Playwright/Juggler only.
- **Generic visible DOM walker:** Replace selector-specific extraction with a walker over visible meaningful DOM nodes. Use size/depth limits to avoid prompt explosions.
- **Separate observability from actionability:** A node can be visible to the model without being safe to click. Only actionable nodes should dispatch click/type/select actions.
- **Chrome as baseline, not dependency:** Use Chrome/CDP only in tests/reports to define expected parity. Do not use Chrome logic at runtime for Camoufox.
- **Real-world missions are final validation:** Wordle/SauceDemo/Wikipedia can validate behavior, but implementation must not branch on those sites.

## Task List

### Phase 1: Diagnostic Foundation

## Task 1: Add generic Chrome-vs-Camoufox fixture comparison

**Description:** Create a local fixture and comparison helper that captures browser state from Chrome and Camoufox for the same generic page. The fixture should include visible static text, ARIA roles, standard state attributes, generic `data-*` attributes, interactive controls, hidden content, and disabled controls.

**Acceptance criteria:**

- [ ] Fixture contains no Wordle names, answer terms, or site-specific selectors.
- [ ] Comparison reports visible text, attributes, interactive indexes, and non-actionable observable nodes.
- [ ] The current Camoufox implementation shows at least one meaningful parity gap before the generic adapter work.

**Verification:**

- [ ] `uv run pytest -q tests/parity`
- [ ] Inspect generated comparison output or assertion message for clear Chrome/Camoufox differences.

**Dependencies:** None

**Files likely touched:**

- `tests/parity/test_chrome_camoufox_dom_parity.py`
- `tests/parity/fixtures/` or inline `tmp_path` fixture

**Estimated scope:** Medium, 2-3 files

## Task 2: Define generic DOM observation contract

**Description:** Turn the fixture comparison into explicit contract assertions for what Camoufox must expose: visible meaningful text, semantic roles, accessible names, state attributes, and actionability metadata.

**Acceptance criteria:**

- [ ] Contract asserts observable non-actionable nodes separately from clickable nodes.
- [ ] Contract includes generic state examples such as `aria-selected`, `aria-checked`, `aria-expanded`, `aria-disabled`, and size-limited `data-*`.
- [ ] Contract excludes hidden/display-none nodes.

**Verification:**

- [ ] `uv run pytest -q tests/parity/test_chrome_camoufox_dom_parity.py`

**Dependencies:** Task 1

**Files likely touched:**

- `tests/parity/test_chrome_camoufox_dom_parity.py`

**Estimated scope:** Small, 1 file

### Checkpoint: Diagnostic Foundation

- [ ] Human reviews the generic contract.
- [ ] The parity gap is documented without relying on Wordle.
- [ ] No runtime implementation has been changed yet.

### Phase 2: Generic Observation Slice

## Task 3: Replace selector-specific extraction with a generic visible DOM walker

**Description:** Implement a generic Playwright/Juggler DOM walker in `CamoufoxSession` that traverses visible meaningful elements and text, captures standard attributes, captures bounded generic `data-*`, and records whether each node is observable-only or actionable.

**Acceptance criteria:**

- [ ] No selector list contains Wordle-specific or app-specific patterns.
- [ ] Visible semantic non-interactive nodes appear in `dom_state.llm_representation()`.
- [ ] Hidden nodes are omitted.
- [ ] Prompt output remains bounded by element/text limits.
- [ ] Existing selector ordinal behavior for interactive elements remains stable.

**Verification:**

- [ ] `uv run pytest -q tests/parity/test_chrome_camoufox_dom_parity.py`
- [ ] `uv run pytest -q tests/integration/test_dom_selector_reliability.py`

**Dependencies:** Task 2

**Files likely touched:**

- `src/browser_use_camoufox/session.py`
- `tests/integration/test_dom_selector_reliability.py`
- `tests/parity/test_chrome_camoufox_dom_parity.py`

**Estimated scope:** Medium, 3 files

## Task 4: Preserve actionability and safe interaction mapping

**Description:** Ensure actionable elements from the generic walker still map to stable selectors and ordinals, while observable-only nodes produce clear diagnostics if clicked.

**Acceptance criteria:**

- [ ] Clickable controls still click by browser-use index.
- [ ] Text inputs still accept `input` and printable `send_keys`.
- [ ] Observable-only nodes cannot be clicked accidentally and return a clear error.
- [ ] Disabled controls are represented as disabled and are not treated as successful actions.

**Verification:**

- [ ] `uv run pytest -q tests/integration/test_dom_selector_reliability.py`
- [ ] `uv run pytest -q tests/parity/test_search_extract_screenshot.py`

**Dependencies:** Task 3

**Files likely touched:**

- `src/browser_use_camoufox/session.py`
- `tests/integration/test_dom_selector_reliability.py`

**Estimated scope:** Small-to-medium, 2 files

### Checkpoint: Generic Observation

- [ ] Generic fixture parity passes.
- [ ] Existing integration/parity tests pass.
- [ ] Review confirms no Wordle selectors or site-specific branches remain.

### Phase 3: Tool and Report Parity

## Task 5: Align tool surfaces with generic observation

**Description:** Update tool-facing outputs so `find_elements`, `evaluate`, and search remain consistent with the generic DOM contract and return machine-readable data where expected.

**Acceptance criteria:**

- [ ] `find_elements` includes the same standard attributes used by observation unless explicitly overridden.
- [ ] `find_elements` text output uses normalized visible text.
- [ ] `evaluate` returns valid JSON for structured values.
- [ ] Search, screenshot, and PDF fallback behavior remain unchanged.

**Verification:**

- [ ] `uv run pytest -q tests/parity/test_search_extract_screenshot.py`

**Dependencies:** Task 3

**Files likely touched:**

- `src/browser_use_camoufox/session.py`
- `tests/parity/test_search_extract_screenshot.py`

**Estimated scope:** Small, 2 files

## Task 6: Add Chrome-vs-Camoufox parity matrix reporting

**Description:** Extend the real-world kit or add a focused script/test helper to report observation/action parity dimensions for Chrome and Camoufox without making live mission success the only signal.

**Acceptance criteria:**

- [ ] Report includes runtime, fixture/page name, visible text parity, attribute parity, actionable count, observable-only count, and action result summary.
- [ ] Report output is JSON and redacts sensitive values.
- [ ] Report can be generated without committing artifacts.

**Verification:**

- [ ] `uv run pytest -q tests/parity`
- [ ] Optional local run: `uv run python scripts/real_world_kit.py --runtime camoufox --mission wikipedia --headless --pause-after-task 0`

**Dependencies:** Tasks 3 and 5

**Files likely touched:**

- `scripts/real_world_kit.py`
- `tests/parity/test_chrome_camoufox_dom_parity.py`

**Estimated scope:** Medium, 2 files

### Checkpoint: Tool and Report Parity

- [ ] Parity tests pass.
- [ ] Generated matrix is understandable by a human reviewer.
- [ ] No generated artifacts are staged.

### Phase 4: Real-World Validation

## Task 7: Run and compare real missions under Chrome and Camoufox

**Description:** Execute the agreed real-world missions under both runtimes and compare pass/fail status, step count, errors, and final verification details.

**Acceptance criteria:**

- [ ] Camoufox passes Wordle without manual intervention.
- [ ] Camoufox passes SauceDemo without manual intervention.
- [ ] Camoufox passes Wikipedia without manual intervention.
- [ ] Chrome reports remain available as baseline comparison.
- [ ] Any remaining errors are annotated as model, site, or runtime issues.

**Verification:**

- [ ] `uv run python scripts/real_world_kit.py --runtime camoufox --mission wordle --mission saucedemo --mission wikipedia --pause-after-task 2`
- [ ] `uv run python scripts/real_world_kit.py --runtime chrome --mission wordle --mission saucedemo --mission wikipedia --pause-after-task 2`

**Dependencies:** Task 6

**Files likely touched:**

- No source changes expected unless validation reveals a bug.

**Estimated scope:** Medium, runtime validation

## Task 8: Final validation and cleanup

**Description:** Run all validators, inspect diffs for boundary violations, remove generated sensitive artifacts, and prepare the change for human review.

**Acceptance criteria:**

- [ ] Lint, format, type check, and full tests pass.
- [ ] `git diff` contains no CDP use, no Wordle-specific extraction selectors, and no secrets/artifacts.
- [ ] `storage_state.json` and generated reports are not staged.
- [ ] Plan/task files reflect completed work or remaining follow-ups.

**Verification:**

- [ ] `uv run ruff check src tests scripts`
- [ ] `uv run ruff format --check src tests scripts`
- [ ] `uv run pyright`
- [ ] `uv run pytest -q`
- [ ] `git status --short`
- [ ] `git diff`

**Dependencies:** Task 7

**Files likely touched:**

- `src/browser_use_camoufox/session.py`
- `tests/**`
- `scripts/real_world_kit.py`
- `SPEC.md`
- `tasks/plan.md`
- `tasks/todo.md`

**Estimated scope:** Small, verification/cleanup

### Checkpoint: Complete

- [ ] Human approves final behavior.
- [ ] Human decides whether to commit and push.
- [ ] If committing, run the required git safety checks before staging.

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Generic DOM walker emits too much content | High | Add element, depth, text, and attribute limits; compare prompt size in tests. |
| Observable-only nodes confuse action selection | High | Clearly mark actionability and block clicks with diagnostic errors. |
| Generic `data-*` capture leaks sensitive values | Medium | Bound length, redact known sensitive names, avoid storage/cookie/localStorage reads. |
| Chrome and Camoufox differ due browser engine behavior | Medium | Classify differences as runtime/site/model; do not force impossible exact equality. |
| Real-world missions are flaky | Medium | Use fixture parity as primary regression guard; missions are final smoke validation. |
| Current uncommitted Wordle-oriented patch contaminates plan | Medium | Replace selector-specific logic during Task 3 and review diffs explicitly. |

## Open Questions

- Should all bounded `data-*` attributes be included, or only state-like `data-*` attributes?
- Should observable-only nodes use normal browser-use indexes with click blocking, or a separate non-action representation?
- Should parity matrix generation live in tests only, in `scripts/real_world_kit.py`, or both?
