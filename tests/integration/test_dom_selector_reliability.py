from pathlib import Path

import pytest
from browser_use.browser.events import BrowserStateRequestEvent, ClickElementEvent, SendKeysEvent, TypeTextEvent

from browser_use_camoufox import CamoufoxSession
from browser_use_camoufox.session import OBSERVABLE_ELEMENT_ATTRIBUTE, SEMANTIC_EVIDENCE_ATTRIBUTE


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
async def test_actionable_nodes_include_bounded_redacted_semantic_evidence(tmp_path: Path):
	fixture = tmp_path / 'semantic_evidence.html'
	long_label = 'Alpha ' * 80
	fixture.write_text(
		f"""
		<html>
			<body>
				<label for="query">Search Terms</label>
				<button
					id="submit"
					type="submit"
					name="lookup"
					title="Run lookup"
					aria-label="{long_label}"
					data-testid="lookup-button"
					data-session-token="must-not-leak"
					data-state="ready"
				>
					Visible lookup action
				</button>
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

		button = next(node for node in state.dom_state.selector_map.values() if node.attributes.get('id') == 'submit')
		evidence = button.attributes.get('data-browser-use-camoufox-semantic-evidence')
		assert evidence is not None
		assert 'visible lookup action' in evidence.lower()
		assert 'aria-label=' in evidence
		assert 'data-testid=lookup-button' in evidence
		assert 'data-state=ready' in evidence
		assert 'data-session-token' not in evidence
		assert 'must-not-leak' not in evidence
		assert len(evidence) <= 240
		assert button.attributes['data-browser-use-camoufox-selector'] == '#submit'
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_semantic_evidence_includes_owner_labels_and_interactable_state(tmp_path: Path):
	fixture = tmp_path / 'semantic_owner_state.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<section aria-label="Checkout Panel">
					<label for="coupon">Coupon code</label>
					<input id="coupon" placeholder="Discount code" value="SAVE10" />
					<button id="apply" aria-label="Apply coupon">Apply</button>
					<button id="locked" aria-disabled="true">Locked apply</button>
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

		input_node = next(
			node for node in state.dom_state.selector_map.values() if node.attributes.get('id') == 'coupon'
		)
		input_evidence = input_node.attributes.get(SEMANTIC_EVIDENCE_ATTRIBUTE, '')
		assert 'label=Coupon code' in input_evidence
		assert 'owner=Checkout Panel' in input_evidence
		assert 'interactable=enabled' in input_evidence
		assert 'role=' in input_evidence
		assert 'geometry=' in input_evidence

		locked = next(node for node in state.dom_state.selector_map.values() if node.attributes.get('id') == 'locked')
		locked_evidence = locked.attributes.get(SEMANTIC_EVIDENCE_ATTRIBUTE, '')
		assert 'owner=Checkout Panel' in locked_evidence
		assert 'interactable=disabled' in locked_evidence
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
async def test_send_keys_normalizes_text_newlines_and_key_chords(tmp_path: Path):
	fixture = tmp_path / 'keyboard-normalized.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<textarea id="target" autofocus></textarea>
				<script>
					document.addEventListener('keydown', (event) => {
						if (event.ctrlKey && event.key.toLowerCase() === 'a') {
							document.body.dataset.ctrlA = 'true';
						}
					});
				</script>
			</body>
		</html>
		"""
	)
	session = CamoufoxSession(headless=True)

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())
		page = await session.get_current_page()

		await session.on_SendKeysEvent(SendKeysEvent(keys='Alpha\nBeta'))
		assert await page.locator('#target').input_value() == 'Alpha\nBeta'

		await session.on_SendKeysEvent(SendKeysEvent(keys='Control+A'))
		assert await page.locator('body').get_attribute('data-ctrl-a') == 'true'
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_send_keys_rejects_ambiguous_key_strings(tmp_path: Path):
	fixture = tmp_path / 'keyboard-invalid.html'
	fixture.write_text('<html><body><input id="target" autofocus /></body></html>')
	session = CamoufoxSession(headless=True)

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())

		with pytest.raises(RuntimeError, match='Ambiguous keyboard input'):
			await session.on_SendKeysEvent(SendKeysEvent(keys='Control+'))
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_send_keys_prepares_generic_app_focus_and_records_active_element_diagnostics(tmp_path: Path):
	fixture = tmp_path / 'keyboard-app-focus.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<div id="app-root" class="game-shell" role="application" aria-label="Puzzle board" tabindex="-1">
					<canvas id="board" aria-label="Board canvas"></canvas>
				</div>
				<script>
					document.addEventListener('keydown', (event) => {
						document.body.dataset.lastKey = event.key;
						document.body.dataset.activeTag = document.activeElement.tagName.toLowerCase();
						document.body.dataset.activeRole = document.activeElement.getAttribute('role') || '';
						document.body.dataset.activeId = document.activeElement.id || '';
					});
				</script>
			</body>
		</html>
		"""
	)
	session = CamoufoxSession(headless=True)

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())
		page = await session.get_current_page()

		await session.on_SendKeysEvent(SendKeysEvent(keys='ArrowRight'))

		assert await page.locator('body').get_attribute('data-last-key') == 'ArrowRight'
		assert await page.locator('body').get_attribute('data-active-tag') == 'div'
		assert await page.locator('body').get_attribute('data-active-role') == 'application'
		assert await page.locator('body').get_attribute('data-active-id') == 'app-root'
		diagnostics = session.last_keyboard_diagnostics
		assert diagnostics is not None
		assert diagnostics['before']['tag'] == 'body'
		assert diagnostics['after']['tag'] == 'div'
		assert diagnostics['after']['role'] == 'application'
		assert diagnostics['after']['id'] == 'app-root'
		assert diagnostics['after']['class'] == 'game-shell'
		assert diagnostics['after']['label_excerpt'] == 'Puzzle board'
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


@pytest.mark.anyio
async def test_state_includes_generic_autocomplete_listbox_options(tmp_path: Path):
	fixture = tmp_path / 'generic_autocomplete.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<label for="destination">Destination</label>
				<input
					id="destination"
					role="combobox"
					aria-controls="suggestions"
					aria-expanded="true"
					value="north"
				/>
				<ul id="suggestions" role="listbox">
					<li role="option" data-value="north-harbor">North Harbor</li>
					<li role="option" data-value="north-hills">North Hills</li>
				</ul>
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

		options = [node for node in state.dom_state.selector_map.values() if node.attributes.get('role') == 'option']
		assert [option.node_value for option in options] == ['North Harbor', 'North Hills']
		assert all(option.snapshot_node is not None and option.snapshot_node.is_clickable for option in options)
		assert 'North Harbor' in state.dom_state.llm_representation()
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_frame_detach_fixture_recreates_target_after_observed_action(tmp_path: Path):
	fixture = tmp_path / 'generic_frame_detach.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<iframe id="dynamic-frame" srcdoc="<button id='target'>Continue</button>"></iframe>
				<script>
					document.body.dataset.ready = 'true';
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
		target = next(node for node in state.dom_state.selector_map.values() if node.node_value == 'Continue')

		page = await session.get_current_page()
		await page.evaluate(
			"""() => {
				document.querySelector('#dynamic-frame').remove();
				const frame = document.createElement('iframe');
				frame.id = 'dynamic-frame';
				frame.srcdoc = [
					`<button id="target" onclick="parent.document.body.dataset.clicked='true'">`,
					'Continue</button>',
				].join('');
				document.body.appendChild(frame);
			}"""
		)

		await session.on_ClickElementEvent(ClickElementEvent(node=target))

		assert await page.locator('body').get_attribute('data-clicked') == 'true'
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_nested_scroll_container_exposes_offscreen_target_for_recovery(tmp_path: Path):
	fixture = tmp_path / 'nested-scroll.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<div
					id="results-pane"
					style="height: 120px; width: 320px; overflow: auto; border: 1px solid black"
					aria-label="Results pane"
				>
					<div style="height: 420px"></div>
					<button id="load-more" onclick="this.textContent='Loaded more results'">Load more results</button>
				</div>
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
			node for node in state.dom_state.selector_map.values() if node.attributes.get('id') == 'load-more'
		)
		evidence = button.attributes.get('data-browser-use-camoufox-semantic-evidence', '')
		assert button.node_value == 'Load more results'
		assert 'Load more results' in state.dom_state.llm_representation()
		assert 'geometry=' in evidence
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_visual_grid_and_keyboard_fixtures_expose_visible_state(tmp_path: Path):
	fixture = tmp_path / 'visual-grid-keyboard.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<section id="board" aria-label="Letter board">
					<div role="grid">
						<div role="row">
							<div role="gridcell" data-row="1" data-col="1" data-state="correct"
								aria-label="A correct">A</div>
							<div role="gridcell" data-row="1" data-col="2" data-state="present"
								aria-label="B present">B</div>
						</div>
						<div role="row">
							<div role="gridcell" data-row="2" data-col="1" data-state="absent"
								aria-label="C absent">C</div>
							<div role="gridcell" data-row="2" data-col="2" data-state="empty"
								aria-label="D empty">D</div>
						</div>
					</div>
				</section>
				<section id="keyboard" aria-label="Keyboard">
					<button data-key="A" data-state="correct">A</button>
					<button data-key="B" data-state="present">B</button>
					<button data-key="C" disabled data-state="absent">C</button>
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

		cells = [node for node in state.dom_state.selector_map.values() if node.attributes.get('role') == 'gridcell']
		keys = [node for node in state.dom_state.selector_map.values() if node.attributes.get('data-key')]
		grid = next(node for node in state.dom_state.selector_map.values() if node.attributes.get('role') == 'grid')
		grid_summary = grid.attributes.get('data-browser-use-camoufox-grid-summary', '')
		assert [(cell.node_value, cell.attributes['data-state']) for cell in cells] == [
			('A', 'correct'),
			('B', 'present'),
			('C', 'absent'),
			('D', 'empty'),
		]
		assert [(key.node_value, key.attributes['data-state']) for key in keys] == [
			('A', 'correct'),
			('B', 'present'),
			('C', 'absent'),
		]
		assert 'aria-label=A correct' in state.dom_state.llm_representation()
		assert [key.attributes['data-key'] for key in keys] == ['A', 'B', 'C']
		assert 'rows=2; columns=2' in grid_summary
		assert 'r1c1=A(correct)' in grid_summary
		assert 'r2c2=D(empty)' in grid_summary
	finally:
		await session.stop()
