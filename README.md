# browser-use-camoufox

[![CI](https://github.com/qmatiaslopez/browser-use-camoufox/actions/workflows/ci.yml/badge.svg)](https://github.com/qmatiaslopez/browser-use-camoufox/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Run [`browser-use`](https://github.com/browser-use/browser-use) agents on [Camoufox](https://github.com/daijro/camoufox) through Playwright-compatible APIs.

`browser-use-camoufox` is an independent compatibility layer for `browser-use==0.12.6`. The upstream `browser-use` project does not currently ship a native Camoufox backend, so this package migrates the supported browser/session surface without pretending Camoufox is Chromium.

> Status: alpha. APIs are intentionally conservative and support Python 3.11 and 3.12.

## Highlights

- Camoufox-backed `BrowserSession` for Browser-Use agents.
- Tool overrides for navigation, click, search, DOM queries, JavaScript evaluation, scrolling, screenshots, PDF export, dropdowns, uploads, and MCP/session helpers.
- Context support for downloads, storage state, extra headers, init scripts, permissions, geolocation, HAR recording, and video recording.
- Stable DOM selector extraction with visibility, disabled-state, ordinal, iframe, and open shadow-root metadata.
- Bounded click/navigation diagnostics for stale targets, top-layer interception, no-change clicks, and committed navigations that outlive Playwright timeouts.
- Explicit unsupported-boundary errors instead of fake CDP shims.

## Install

From GitHub before the first PyPI release:

```bash
uv add "browser-use-camoufox @ git+https://github.com/qmatiaslopez/browser-use-camoufox.git"
uv run camoufox fetch
uv run browser-use-camoufox doctor
```

After the package is available on PyPI:

```bash
uv add browser-use-camoufox
uv run camoufox fetch
uv run browser-use-camoufox doctor
```

## Quick start

```python
from browser_use import Agent
from browser_use.tools.service import Tools
from browser_use_camoufox import CamoufoxSession, register_camoufox_tools

llm = ...  # Configure any browser-use-compatible LLM.

browser_session = CamoufoxSession(
	headless=False,
	accept_downloads=True,
	record_har_path='artifacts/session.har',
	record_har_content='embed',
	record_har_mode='full',
	record_video_dir='artifacts/videos',
	record_video_size={'width': 1280, 'height': 720},
)

tools = Tools()
register_camoufox_tools(tools)

agent = Agent(
	task='Complete the browser task',
	llm=llm,
	browser_session=browser_session,
	tools=tools,
)

await agent.run()
```

## Compatibility surface

Run the machine-readable inventory and current fixture conformance matrix:

```bash
uv run browser-use-camoufox compatibility --surface-inventory
uv run browser-use-camoufox conformance --matrix current --fixtures-only
```

The migrated surface includes navigation, tabs, click, type, scroll, scroll-to-text, coordinate click, dropdowns, uploads, storage, screenshots, HTML extraction, page search, element lookup, JavaScript evaluation, and PDF export when the active Camoufox Playwright runtime exposes `page.pdf()`.

## No fake CDP boundary

No fake CDP client, fake raw CDP session, or fake CDP domain object is provided. Raw CDP access, captcha hooks, tracing, profiling, coverage, closed shadow-root internals, and Chromium-only profile flags are rejected with actionable guidance instead of being silently accepted.

Unsupported old profile mappings include `traces_dir`, `proxy`, `disable_security`, and `deterministic_rendering`.

## Validation

```bash
uv sync
uv run pytest -v tests/unit tests/integration tests/parity
uv run browser-use-camoufox doctor
uv run browser-use-camoufox compatibility --surface-inventory
uv run browser-use-camoufox conformance --matrix current --fixtures-only
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run pyright
uv build
uv run python -m pip check
```

Runtime smoke checks require the Camoufox browser build:

```bash
uv run camoufox fetch
uv run browser-use-camoufox doctor --runtime-smoke
```

## Real-world benchmark semantics

`scripts/real_world_kit.py` is a live validation harness for Chrome and Camoufox. A mission passes only when the agent itself finishes with `done(success=True)` and the verifier also passes. Verifier evidence is diagnostic; it must not be converted into synthetic agent success after `Agent.run()`.
