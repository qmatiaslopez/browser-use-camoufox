from pathlib import Path

import pytest
from browser_use.browser.events import (
	BrowserStateRequestEvent,
	ClickElementEvent,
	ScrollEvent,
	SendKeysEvent,
	TypeTextEvent,
)
from browser_use.tools.views import ScrollAction

from browser_use_camoufox import CamoufoxSession


@pytest.mark.anyio
async def test_camoufox_state_selector_map_and_basic_actions(tmp_path: Path):
	fixture = tmp_path / 'actions.html'
	fixture.write_text(
		"""
		<html>
			<head><title>Actions</title></head>
			<body style="height: 2000px">
				<button id="click-me" onclick="this.textContent = 'Clicked'">Click me</button>
				<input id="name" />
				<div style="margin-top: 1500px">Bottom</div>
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

		dom_text = state.dom_state.llm_representation()
		assert 'Empty DOM tree' not in dom_text
		assert '[1]<button' in dom_text
		assert '[2]<input' in dom_text

		button = next(node for node in state.dom_state.selector_map.values() if node.attributes.get('id') == 'click-me')
		input_node = next(node for node in state.dom_state.selector_map.values() if node.attributes.get('id') == 'name')

		await session.event_bus.dispatch(ClickElementEvent(node=button))
		await session.event_bus.dispatch(TypeTextEvent(node=input_node, text='Ada'))
		await session.event_bus.dispatch(SendKeysEvent(keys='Enter'))
		await session.event_bus.dispatch(ScrollEvent(direction='down', amount=400))

		page = await session.get_current_page()
		assert await page.locator('#click-me').text_content() == 'Clicked'
		assert await page.locator('#name').input_value() == 'Ada'
		assert await page.evaluate('window.scrollY') > 0
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_camoufox_indexed_scroll_targets_nearest_scroll_container(tmp_path: Path):
	fixture = tmp_path / 'nested_scroll.html'
	fixture.write_text(
		"""
		<html>
			<body style="height: 1600px">
				<section
					id="left"
					style="height: 180px; overflow: auto; border: 1px solid black"
				>
					<button id="left-top">Left top</button>
					<div style="height: 900px"></div>
				</section>
				<section
					id="right"
					style="height: 180px; overflow: auto; border: 1px solid black"
				>
					<button id="right-top">Right top</button>
					<div style="height: 900px"></div>
				</section>
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
		right_button = next(
			node for node in state.dom_state.selector_map.values() if node.attributes.get('id') == 'right-top'
		)

		await session.event_bus.dispatch(ScrollEvent(direction='down', amount=120, node=right_button))

		page = await session.get_current_page()
		assert await page.evaluate("document.querySelector('#right').scrollTop") == 120
		assert await page.evaluate("document.querySelector('#left').scrollTop") == 0
		assert await page.evaluate('window.scrollY') == 0
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_camoufox_scroll_action_reports_noop_diagnostics(tmp_path: Path):
	fixture = tmp_path / 'noop_scroll.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<button id="only">Only button</button>
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
		button = next(node for node in state.dom_state.selector_map.values() if node.attributes.get('id') == 'only')

		result = await session.scroll_action(ScrollAction(down=True, num_pages=1, index=button.node_id))

		assert result.metadata is not None
		diagnostics = result.metadata['scroll_diagnostics']
		assert diagnostics['target_index'] == button.node_id
		assert diagnostics['blocker'] == 'already_at_boundary'
		assert diagnostics['before']['x'] == 0
		assert diagnostics['before']['max_y'] == 0
		assert diagnostics['after']['y'] == 0
		assert 'no-op' in result.extracted_content
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_camoufox_rejects_file_inputs_with_actionable_error(tmp_path: Path):
	fixture = tmp_path / 'file.html'
	fixture.write_text('<html><body><input id="upload" type="file" /></body></html>')

	session = CamoufoxSession(headless=True)

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())

		state_event = session.event_bus.dispatch(BrowserStateRequestEvent(include_dom=True, include_screenshot=False))
		await state_event
		state = await state_event.event_result()
		file_input = next(
			node for node in state.dom_state.selector_map.values() if node.attributes.get('id') == 'upload'
		)

		click_event = session.event_bus.dispatch(ClickElementEvent(node=file_input))
		await click_event

		with pytest.raises(RuntimeError, match='File inputs require upload support'):
			await click_event.event_result()
	finally:
		await session.stop()
