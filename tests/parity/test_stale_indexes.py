from pathlib import Path

import pytest
from browser_use.browser.events import BrowserStateRequestEvent
from browser_use.tools.service import Tools

from browser_use_camoufox import CamoufoxSession, register_camoufox_tools


@pytest.mark.anyio
async def test_click_refreshes_stale_selector_index_before_failing(tmp_path: Path):
	fixture = tmp_path / 'stale.html'
	fixture.write_text('<html><body><button id="old">Old</button></body></html>')
	tools = Tools()
	register_camoufox_tools(tools)
	session = CamoufoxSession(headless=True)

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())
		state_event = session.event_bus.dispatch(BrowserStateRequestEvent(include_dom=True, include_screenshot=False))
		await state_event
		state = await state_event.event_result()
		old_index = next(
			index for index, node in state.dom_state.selector_map.items() if node.attributes.get('id') == 'old'
		)

		page = await session.get_current_page()
		await page.evaluate(
			"""() => {
				document.body.innerHTML = '<button id="new">New</button>';
				document.querySelector('#new').addEventListener('click', event => event.target.textContent = 'Clicked');
			}"""
		)
		click_result = await tools.registry.execute_action('click', {'index': old_index}, browser_session=session)

		assert click_result.error is None
		assert await page.locator('#new').text_content() == 'Clicked'
	finally:
		await session.stop()
