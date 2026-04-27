## 2026-04-26

- Completed Task 3: replaced selector-specific observable extraction with a generic visible DOM walker.
- Added generic DOM parity coverage for visible semantic text, ARIA state, bounded `data-*`, observable-only nodes, hidden-node exclusion, and clickable separation.
- Verified `uv run pytest -q`, `uv run ruff check src tests scripts`, `uv run ruff format --check src tests scripts`, `uv run pyright`, and `uv build` pass.
