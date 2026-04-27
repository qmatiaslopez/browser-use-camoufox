from pathlib import Path

import pytest
from browser_use.browser.events import BrowserStateRequestEvent, ClickElementEvent

from browser_use_camoufox import CamoufoxSession


@pytest.mark.anyio
async def test_selector_map_uses_stable_ordinals_and_metadata(tmp_path: Path):
	fixture = tmp_path / 'selectors.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<button class="choice" onclick="this.textContent = 'First clicked'">First</button>
				<button class="choice" onclick="this.textContent = 'Second clicked'">Second</button>
				<button id="hidden" style="display: none">Hidden</button>
				<button id="disabled" disabled>Disabled</button>
			</body>
		</html>
		"""
	)
	session = CamoufoxSession(headless=True)

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())
		state_event = session.event_bus.dispatch(BrowserStateRequestEvent(include_dom=True, include_screenshot=False))
		await state_event
		state = await state_event.event_result()

		choices = [node for node in state.dom_state.selector_map.values() if node.attributes.get('class') == 'choice']
		assert [node.attributes['data-browser-use-camoufox-selector'] for node in choices] == ['button', 'button']
		assert [node.attributes['data-browser-use-camoufox-ordinal'] for node in choices] == ['0', '1']
		assert all(node.is_visible for node in choices)
		disabled = next(
			node for node in state.dom_state.selector_map.values() if node.attributes.get('id') == 'disabled'
		)
		assert disabled.attributes['disabled'] == ''
		assert disabled.attributes['data-browser-use-camoufox-disabled'] == 'true'
		assert not any(node.attributes.get('id') == 'hidden' for node in state.dom_state.selector_map.values())

		await session.event_bus.dispatch(ClickElementEvent(node=choices[1]))
		page = await session.get_current_page()
		assert await page.locator('button').nth(1).text_content() == 'Second clicked'
	finally:
		await session.stop()
