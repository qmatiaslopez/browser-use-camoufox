from pathlib import Path

import pytest
from browser_use.browser.events import GoBackEvent, GoForwardEvent, RefreshEvent, WaitEvent

from browser_use_camoufox import CamoufoxSession


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
