from pathlib import Path

import pytest
from browser_use.browser.events import GoBackEvent, GoForwardEvent, NavigateToUrlEvent, RefreshEvent, WaitEvent
from playwright.async_api import Error as PlaywrightError

from browser_use_camoufox import CamoufoxSession

COMMITTED_NAVIGATION_TIMEOUT = 'Timeout after commit'


async def force_goto_timeout_after_commit(session: CamoufoxSession, monkeypatch) -> None:
	page = await session.get_current_page()
	original_goto = page.goto

	async def goto_then_timeout(url, **kwargs):
		await original_goto(url, wait_until='commit')
		raise PlaywrightError(COMMITTED_NAVIGATION_TIMEOUT)

	monkeypatch.setattr(page, 'goto', goto_then_timeout)


@pytest.mark.anyio
async def test_camoufox_session_event_routing_handles_history_refresh_and_wait(tmp_path: Path):
	first = tmp_path / 'first.html'
	second = tmp_path / 'second.html'
	first.write_text(
		f'<html><head><title>First</title></head><body><a href="{second.as_uri()}">Second</a>First</body></html>'
	)
	second.write_text(
		'<html><head><title>Second</title></head><body>'
		'<script>window.name = String((Number(window.name) || 0) + 1)</script>'
		'Second</body></html>'
	)

	session = CamoufoxSession(headless=True)

	try:
		await session.start()
		await session.navigate_to(first.as_uri())
		await session.navigate_to(second.as_uri())

		go_back = session.event_bus.dispatch(GoBackEvent())
		await go_back.event_result(raise_if_none=False)
		assert await session.get_current_page_url() == first.as_uri()
		assert await session.get_current_page_title() == 'First'

		go_forward = session.event_bus.dispatch(GoForwardEvent())
		await go_forward.event_result(raise_if_none=False)
		assert await session.get_current_page_url() == second.as_uri()
		assert await session.get_current_page_title() == 'Second'

		before_refresh = await session.evaluate_script('() => window.name')
		refresh = session.event_bus.dispatch(RefreshEvent())
		await refresh.event_result(raise_if_none=False)
		refresh_count = await session.evaluate_script('() => window.name')
		assert int(refresh_count.extracted_content) > int(before_refresh.extracted_content)

		wait = session.event_bus.dispatch(WaitEvent(seconds=0.01, max_seconds=1.0))
		await wait.event_result(raise_if_none=False)
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_navigation_timeout_is_tolerated_when_target_url_committed(monkeypatch, tmp_path: Path):
	target = tmp_path / 'committed.html'
	target.write_text('<html><head><title>Committed</title></head><body>Ready</body></html>')
	session = CamoufoxSession(headless=True)

	try:
		await session.start()
		await force_goto_timeout_after_commit(session, monkeypatch)

		navigate = session.event_bus.dispatch(NavigateToUrlEvent(url=target.as_uri(), timeout_ms=1))
		await navigate.event_result(raise_if_none=False)

		assert await session.get_current_page_url() == target.as_uri()
		assert await session.get_current_page_title() == 'Committed'
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_navigate_action_reports_committed_page_after_timeout(monkeypatch, tmp_path: Path):
	target = tmp_path / 'action-committed.html'
	target.write_text('<html><head><title>Action committed</title></head><body>Ready</body></html>')
	session = CamoufoxSession(headless=True)

	try:
		await session.start()
		await force_goto_timeout_after_commit(session, monkeypatch)

		result = await session.navigate_action(target.as_uri())

		assert await session.get_current_page_url() == target.as_uri()
		assert result.long_term_memory is not None
		assert 'Action committed' in result.long_term_memory
		assert target.as_uri() in result.long_term_memory
	finally:
		await session.stop()
