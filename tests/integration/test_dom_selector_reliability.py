from pathlib import Path

import pytest
from browser_use.browser.events import BrowserStateRequestEvent, ClickElementEvent, SendKeysEvent, TypeTextEvent

from browser_use_camoufox import CamoufoxSession
from browser_use_camoufox.session import OBSERVABLE_ELEMENT_ATTRIBUTE


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
		assert disabled.attributes['data-browser-use-camoufox-observable'] == 'true'
		assert disabled.snapshot_node is not None
		assert disabled.snapshot_node.is_clickable is False
		assert not any(node.attributes.get('id') == 'hidden' for node in state.dom_state.selector_map.values())

		await session.event_bus.dispatch(ClickElementEvent(node=choices[1]))
		page = await session.get_current_page()
		assert await page.locator('button').nth(1).text_content() == 'Second clicked'

		with pytest.raises(RuntimeError, match='disabled and cannot be clicked'):
			await session.on_ClickElementEvent(ClickElementEvent(node=disabled))
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
async def test_state_grid_cells_are_observable_with_state_and_labels(tmp_path: Path):
	fixture = tmp_path / 'state-grid.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<div id="board">
					<div data-testid="state-cell" data-state="accepted" aria-label="Alpha accepted">A</div>
					<div data-testid="state-cell" data-state="pending" aria-label="Beta pending">B</div>
					<div data-testid="state-cell" data-state="rejected" aria-label="Gamma rejected">C</div>
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

		cells = [
			node for node in state.dom_state.selector_map.values() if node.attributes.get('data-testid') == 'state-cell'
		]
		assert [cell.node_value for cell in cells] == ['A', 'B', 'C']
		assert [cell.attributes['data-state'] for cell in cells] == ['accepted', 'pending', 'rejected']
		assert [cell.attributes['aria-label'] for cell in cells] == [
			'Alpha accepted',
			'Beta pending',
			'Gamma rejected',
		]
		assert all(cell.attributes['data-browser-use-camoufox-observable'] == 'true' for cell in cells)
		assert 'data-state=accepted' in state.dom_state.llm_representation()

		with pytest.raises(RuntimeError, match='observable but not clickable'):
			await session.on_ClickElementEvent(ClickElementEvent(node=cells[0]))
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


@pytest.mark.anyio
async def test_dense_page_keeps_main_semantic_content_when_observation_is_bounded(tmp_path: Path):
	fixture = tmp_path / 'dense.html'
	repeated_nav = '\n'.join(
		f'<a class="side-link" href="#nav-{index}">Navigation filter {index}</a>' for index in range(360)
	)
	fixture.write_text(
		f"""
		<html>
			<body>
				<nav aria-label="Filters">
					{repeated_nav}
				</nav>
				<main>
					<article data-testid="primary-card" data-state="ready">
						<h2>Primary result card</h2>
						<p>Central semantic answer survives bounded output</p>
					</article>
					<ul aria-label="Central list">
						<li data-testid="main-list-item">Important central list item</li>
					</ul>
				</main>
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

		llm_text = state.dom_state.llm_representation()
		assert 'Primary result card' in llm_text
		assert 'Central semantic answer survives bounded output' in llm_text
		assert 'Important central list item' in llm_text
		assert 'data-state=ready' in llm_text
		assert len(state.dom_state.selector_map) <= 300
		assert (
			sum(1 for node in state.dom_state.selector_map.values() if node.attributes.get('class') == 'side-link')
			< 300
		)

		primary_card = next(
			node
			for node in state.dom_state.selector_map.values()
			if node.attributes.get('data-testid') == 'primary-card'
		)
		assert primary_card.attributes[OBSERVABLE_ELEMENT_ATTRIBUTE] == 'true'
		assert primary_card.snapshot_node is not None
		assert primary_card.snapshot_node.is_clickable is False
		with pytest.raises(RuntimeError, match='observable but not clickable'):
			await session.on_ClickElementEvent(ClickElementEvent(node=primary_card))
	finally:
		await session.stop()
