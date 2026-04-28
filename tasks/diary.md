# Project Diary

## 2026-04-28

- Completed Task 1 fixtures for general Camoufox runtime intelligence.
- Added generic coverage for dense cards, non-ARIA autocomplete suggestions, top-layer intercepted clicks, nested scroll containers, and visual grid/keyboard state.
- Added minimal supporting runtime evidence so the new fixtures expose bounded child/group evidence, geometry, and visible suggestion/key metadata.
- Validators passed: `uv run ruff check src tests scripts`, `uv run ruff format --check src tests scripts`, `uv run pyright`, targeted pytest suite, and `uv build`.
- Completed Task 2 semantic model helpers.
- Semantic evidence now includes labels, owner context, implicit role, geometry, and enabled/disabled interactable state while preserving sensitive attribute redaction and bounded text.
- Validators passed: `uv run ruff check src tests scripts`, `uv run ruff format --check src tests scripts`, `uv run pyright`, `uv run pytest -q tests/unit/test_diagnostics.py tests/integration/test_dom_selector_reliability.py tests/parity/test_chrome_camoufox_dom_parity.py`, and `uv build`.
- Completed Task 3 grouped card/list extraction.
- `find_elements` now emits compact grouped evidence for card-like results, including title, primary link, price-like visible metadata, and actions while preserving existing child evidence.
- Validators passed: `uv run ruff check src tests scripts`, `uv run ruff format --check src tests scripts`, `uv run pyright`, `uv run pytest -q tests/parity/test_search_extract_screenshot.py tests/integration/test_dom_selector_reliability.py`, and `uv build`.
- Completed Task 4 grouped evidence for action relocalization diagnostics.
- Existing stale-index coverage confirms repeated-card relocalization preserves the intended grouped action and ambiguous duplicates fail with bounded ranked diagnostics.
- Validators passed: `uv run pytest -q tests/parity/test_stale_indexes.py tests/integration/test_dom_selector_reliability.py`, `uv run ruff check src tests scripts`, `uv run ruff format --check src tests scripts`, `uv run pyright`, and `uv build`.
- Completed Task 5 conservative action planner diagnostics.
- Last-click diagnostics now include bounded action-plan strategy, preconditions, attempted steps, result, and classified no-change reason while preserving existing click, keyboard, autocomplete, form-submit, and frame-detach behavior.
- Validators passed: `uv run pytest -q tests/integration/test_interaction_events.py tests/parity/test_stale_indexes.py tests/parity/test_iframe_dom.py`, `uv run ruff check src tests scripts`, `uv run ruff format --check src tests scripts`, `uv run pyright`, and `uv build`.
- Completed Task 6 non-ARIA overlay/autocomplete selection.
- Click recovery now recognizes visible custom suggestions with `data-value`, selects the intended value through its owning input, and preserves existing ARIA option/menu behavior.
- Validators passed: `uv run pytest -q tests/integration/test_interaction_events.py tests/parity/test_forms_dropdown_upload.py`, `uv run ruff check src tests scripts`, `uv run ruff format --check src tests scripts`, `uv run pyright`, and `uv build`.
- Completed Task 7 hit-target, top-layer, and scroll-container recovery.
- Click handling now validates the intended hit target before direct clicks, classifies top-layer blockers without unsafe fallback clicks, and coordinate clicks reject non-interactive hit targets before dispatch.
- Nested scroll-container coverage confirms scrolling the nearest container allows the intended target click.
- Validators passed: `uv run pytest -q tests/integration/test_interaction_events.py tests/integration/test_dom_selector_reliability.py`, `uv run ruff check src tests scripts`, `uv run ruff format --check src tests scripts`, `uv run pyright`, and `uv build`.
