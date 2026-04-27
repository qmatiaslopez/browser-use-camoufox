from pathlib import Path

import pytest
from browser_use.browser.events import (
	BrowserStateRequestEvent,
	ClickCoordinateEvent,
	ScrollToTextEvent,
)

from browser_use_camoufox import CamoufoxSession


@pytest.mark.anyio
async def test_camoufox_scroll_to_text_and_coordinate_click(tmp_path: Path):
	fixture = tmp_path / 'advanced_interactions.html'
	fixture.write_text(
		"""
		<html>
			<head><title>Advanced interactions</title></head>
			<body style="height: 2400px">
				<button
					id="target"
					style="position:absolute; left: 40px; top: 1850px; width: 140px; height: 40px"
					onclick="this.textContent = 'Coordinate clicked'"
				>
					Distant target
				</button>
			</body>
		</html>
		"""
	)

	session = CamoufoxSession(headless=True)

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())

		scroll_event = session.event_bus.dispatch(ScrollToTextEvent(text='Distant target'))
		await scroll_event

		page = await session.get_current_page()
		rect = await page.locator('#target').bounding_box()
		assert rect is not None

		click_event = session.event_bus.dispatch(
			ClickCoordinateEvent(coordinate_x=int(rect['x'] + 10), coordinate_y=int(rect['y'] + 10))
		)
		await click_event
		result = await click_event.event_result()

		assert result == {'click_x': int(rect['x'] + 10), 'click_y': int(rect['y'] + 10)}
		assert await page.locator('#target').text_content() == 'Coordinate clicked'
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_camoufox_highlight_interaction_element_marks_and_clears_node(tmp_path: Path):
	fixture = tmp_path / 'highlight.html'
	fixture.write_text(
		"""
		<html>
			<head><title>Highlight</title></head>
			<body>
				<button id="target">Highlight me</button>
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
		button = next(node for node in state.dom_state.selector_map.values() if node.attributes.get('id') == 'target')

		await session.highlight_interaction_element(button)

		page = await session.get_current_page()
		assert await page.locator('[data-browser-use-camoufox-highlight]').count() == 1
		assert await page.locator('#target').evaluate("element => element.style.outline.includes('rgb(255, 152, 0)')")
	finally:
		await session.stop()
