## 2026-04-26

- Completed Task 3: replaced selector-specific observable extraction with a generic visible DOM walker.
- Added generic DOM parity coverage for visible semantic text, ARIA state, bounded `data-*`, observable-only nodes, hidden-node exclusion, and clickable separation.
- Completed Task 4: preserved actionability boundaries by keeping observable-only nodes readable but not editable/clickable, while inputs and printable `send_keys` remain usable.
- Completed Task 5: aligned Camoufox tool surfaces with generic observation; verified `find_elements` defaults expose standard ARIA/data state and normalized visible text, `evaluate` returns JSON for structured values, and search/screenshot/PDF behavior remains stable.
- Completed Task 6: added JSON Chrome-vs-Camoufox parity matrix reporting helpers with visible text parity, attribute parity, actionable/observable counts, action result summaries, and sensitive-key redaction.
- Verified `uv run pytest -q tests/parity`, `uv run pytest -q`, `uv run ruff check src tests scripts`, `uv run ruff format --check src tests scripts`, `uv run pyright`, and `uv build` pass.
