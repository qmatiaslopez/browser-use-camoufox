from pathlib import Path

import pytest
from browser_use.browser.events import BrowserStateRequestEvent, ClickElementEvent, SendKeysEvent, TypeTextEvent

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


@pytest.mark.anyio
async def test_send_keys_types_printable_words_but_presses_special_keys(tmp_path: Path):
	fixture = tmp_path / 'keyboard.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<input id="target" autofocus />
			</body>
		</html>
		"""
	)
	session = CamoufoxSession(headless=True)

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())
		await session.on_SendKeysEvent(SendKeysEvent(keys='SLATE'))
		value = await (await session.get_current_page()).locator('#target').input_value()
		assert value == 'SLATE'

		await session.on_SendKeysEvent(SendKeysEvent(keys='Backspace'))
		value = await (await session.get_current_page()).locator('#target').input_value()
		assert value == 'SLAT'
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_wordle_like_tiles_are_observable_with_state_and_labels(tmp_path: Path):
	fixture = tmp_path / 'wordle.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<div id="board">
					<div data-testid="tile" data-state="correct" aria-label="G correct">G</div>
					<div data-testid="tile" data-state="present" aria-label="L present">L</div>
					<div data-testid="tile" data-state="absent" aria-label="O absent">O</div>
				</div>
				<button id="enter">Enter</button>
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

		tiles = [node for node in state.dom_state.selector_map.values() if node.attributes.get('data-testid') == 'tile']
		assert [tile.node_value for tile in tiles] == ['G', 'L', 'O']
		assert [tile.attributes['data-state'] for tile in tiles] == ['correct', 'present', 'absent']
		assert [tile.attributes['aria-label'] for tile in tiles] == ['G correct', 'L present', 'O absent']
		assert all(tile.attributes['data-browser-use-camoufox-observable'] == 'true' for tile in tiles)
		assert 'data-state=correct' in state.dom_state.llm_representation()

		with pytest.raises(RuntimeError, match='observable but not clickable'):
			await session.on_ClickElementEvent(ClickElementEvent(node=tiles[0]))
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_click_failure_includes_selector_diagnostics(tmp_path: Path):
	fixture = tmp_path / 'covered.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<button id="blocked">Blocked</button>
				<div style="
					position: fixed;
					inset: 0;
					background: rgba(0, 0, 0, 0.1);
					z-index: 9999;
				"></div>
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
		button = next(node for node in state.dom_state.selector_map.values() if node.attributes.get('id') == 'blocked')

		with pytest.raises(RuntimeError, match='Camoufox click failed after 5000ms'):
			await session.on_ClickElementEvent(ClickElementEvent(node=button))
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_type_text_rejects_observable_only_nodes_but_accepts_text_inputs(tmp_path: Path):
	fixture = tmp_path / 'actionability.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<p id="status" data-state="idle">Status text</p>
				<input id="name" />
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
		status = next(node for node in state.dom_state.selector_map.values() if node.attributes.get('id') == 'status')
		input_node = next(node for node in state.dom_state.selector_map.values() if node.attributes.get('id') == 'name')

		with pytest.raises(RuntimeError, match='observable but not editable'):
			await session.on_TypeTextEvent(TypeTextEvent(node=status, clear=True, text='ignored'))

		await session.on_TypeTextEvent(TypeTextEvent(node=input_node, clear=True, text='Ada'))
		page = await session.get_current_page()
		assert await page.locator('#name').input_value() == 'Ada'
	finally:
		await session.stop()
