from pathlib import Path

import pytest
from browser_use.browser.events import BrowserStateRequestEvent, ClickElementEvent, TypeTextEvent

from browser_use_camoufox import CamoufoxSession


@pytest.mark.anyio
async def test_open_shadow_root_elements_are_visible_and_interactive(tmp_path: Path):
	fixture = tmp_path / 'shadow.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<open-widget></open-widget>
				<script>
					const host = document.querySelector('open-widget');
					const root = host.attachShadow({mode: 'open'});
					root.innerHTML = `
						<button id="shadow-button" onclick="this.textContent = 'Clicked in shadow'">
							Shadow button
						</button>
						<input id="shadow-input" />
					`;
				</script>
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

		button = next(
			node for node in state.dom_state.selector_map.values() if node.attributes.get('id') == 'shadow-button'
		)
		input_node = next(
			node for node in state.dom_state.selector_map.values() if node.attributes.get('id') == 'shadow-input'
		)
		assert button.shadow_root_type == 'open'
		assert button.attributes['data-browser-use-camoufox-shadow-root'] == 'open'

		await session.event_bus.dispatch(ClickElementEvent(node=button))
		await session.event_bus.dispatch(TypeTextEvent(node=input_node, text='inside shadow'))

		page = await session.get_current_page()
		assert await page.locator('#shadow-button').text_content() == 'Clicked in shadow'
		assert await page.locator('#shadow-input').input_value() == 'inside shadow'

	finally:
		await session.stop()


@pytest.mark.anyio
async def test_closed_shadow_roots_are_classified_explicitly(tmp_path: Path):
	fixture = tmp_path / 'closed-shadow.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<closed-widget id="closed-host"></closed-widget>
				<script>
					const host = document.querySelector('closed-widget');
					const root = host.attachShadow({mode: 'closed'});
					root.innerHTML = '<button id="closed-shadow-button">Closed shadow button</button>';
				</script>
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

		closed_shadow_buttons = [
			node
			for node in state.dom_state.selector_map.values()
			if node.attributes.get('id') == 'closed-shadow-button'
		]
		assert closed_shadow_buttons == []
		closed_hosts = [
			node
			for node in state.dom_state.selector_map.values()
			if node.attributes.get('data-browser-use-camoufox-shadow-root') == 'closed'
		]
		assert len(closed_hosts) == 1
		assert closed_hosts[0].attributes.get('id') == 'closed-host'
		assert closed_hosts[0].shadow_root_type == 'closed'
	finally:
		await session.stop()
