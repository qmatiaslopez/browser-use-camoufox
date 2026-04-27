from pathlib import Path

import pytest
from browser_use.browser.events import (
	BrowserStateRequestEvent,
	ClickCoordinateEvent,
	ClickElementEvent,
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


@pytest.mark.anyio
async def test_click_records_bounded_post_click_change_diagnostics(tmp_path: Path):
	fixture = tmp_path / 'click_diagnostics.html'
	fixture.write_text(
		"""
		<html>
			<head><title>Before click</title></head>
			<body>
				<button
					id="target"
					data-state="ready"
					data-token="secret-token-value"
					onclick="
						this.setAttribute('data-state', 'done');
						document.title = 'After click';
						document.querySelector('#status').textContent = 'Clicked result visible';
						document.body.appendChild(document.createElement('section')).textContent = 'New panel';
					"
				>
					Run action
				</button>
				<p id="status">Waiting result</p>
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

		await session.on_ClickElementEvent(ClickElementEvent(node=button))

		diagnostics = session.last_click_diagnostics
		assert diagnostics is not None
		assert diagnostics['url_changed'] is False
		assert diagnostics['title'] == {'before': 'Before click', 'after': 'After click', 'changed': True}
		assert diagnostics['dom_count']['after'] > diagnostics['dom_count']['before']
		assert diagnostics['visible_text_change']['changed'] is True
		assert 'Clicked result visible' in diagnostics['visible_text_change']['after_excerpt']
		assert diagnostics['target_attributes']['before']['data-state'] == 'ready'
		assert diagnostics['target_attributes']['after']['data-state'] == 'done'
		assert 'data-token' not in diagnostics['target_attributes']['before']
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_click_recovers_when_primary_click_times_out_but_keyboard_activation_submits(tmp_path: Path):
	fixture = tmp_path / 'generic_search_timeout.html'
	fixture.write_text(
		"""
		<html>
			<head><title>Generic search timeout</title></head>
			<body>
				<form id="search-form">
					<label for="query">Search knowledge base</label>
					<input id="query" name="q" value="runtime diagnostics" />
					<button id="search-button" type="submit">Search</button>
				</form>
				<p id="result">Waiting</p>
				<script>
					const button = document.querySelector('#search-button');
					button.addEventListener('pointerdown', (event) => {
						event.preventDefault();
						button.style.pointerEvents = 'none';
					}, { capture: true });
					document.querySelector('#search-form').addEventListener('submit', (event) => {
						event.preventDefault();
						document.querySelector('#result').textContent = 'Submitted runtime diagnostics';
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
		state_event = session.event_bus.dispatch(BrowserStateRequestEvent(include_dom=True, include_screenshot=False))
		await state_event
		state = await state_event.event_result()
		button = next(
			node for node in state.dom_state.selector_map.values() if node.attributes.get('id') == 'search-button'
		)

		await session.on_ClickElementEvent(ClickElementEvent(node=button))

		page = await session.get_current_page()
		assert await page.locator('#result').text_content() == 'Submitted runtime diagnostics'
		diagnostics = session.last_click_diagnostics
		assert diagnostics is not None
		assert diagnostics['fallback']['attempted'] == ['click', 'keyboard_activation']
		assert diagnostics['fallback']['result'] == 'keyboard_activation_succeeded'
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_click_recovers_with_associated_form_submit_when_activation_does_not_submit(tmp_path: Path):
	fixture = tmp_path / 'generic_form_submit_fallback.html'
	fixture.write_text(
		"""
		<html>
			<head><title>Generic form submit fallback</title></head>
			<body>
				<form id="unrelated-form">
					<input id="other-query" name="q" value="unrelated" />
					<button id="other-button" type="submit">Other search</button>
				</form>
				<form id="search-form">
					<label for="query">Search knowledge base</label>
					<input id="query" name="q" value="runtime diagnostics" />
					<button id="search-button" type="submit">Search</button>
				</form>
				<p id="result">Waiting</p>
				<script>
					document.querySelector('#search-button').addEventListener('click', (event) => {
						event.preventDefault();
					});
					document.querySelector('#search-button').addEventListener('keydown', (event) => {
						if (event.key === ' ' || event.key === 'Enter') event.preventDefault();
					});
					document.querySelector('#unrelated-form').addEventListener('submit', (event) => {
						event.preventDefault();
						document.querySelector('#result').textContent = 'Submitted unrelated form';
					});
					document.querySelector('#search-form').addEventListener('submit', (event) => {
						event.preventDefault();
						document.querySelector('#result').textContent = 'Submitted runtime diagnostics';
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
		state_event = session.event_bus.dispatch(BrowserStateRequestEvent(include_dom=True, include_screenshot=False))
		await state_event
		state = await state_event.event_result()
		button = next(
			node for node in state.dom_state.selector_map.values() if node.attributes.get('id') == 'search-button'
		)

		await session.on_ClickElementEvent(ClickElementEvent(node=button))

		page = await session.get_current_page()
		assert await page.locator('#result').text_content() == 'Submitted runtime diagnostics'
		diagnostics = session.last_click_diagnostics
		assert diagnostics is not None
		assert diagnostics['fallback']['attempted'] == ['click', 'keyboard_activation', 'form_submit']
		assert diagnostics['fallback']['result'] == 'form_submit_succeeded'
	finally:
		await session.stop()
