from pathlib import Path

import pytest
from browser_use.browser.events import (
	BrowserStateRequestEvent,
	ClickCoordinateEvent,
	ClickElementEvent,
	ScrollEvent,
	ScrollToTextEvent,
)
from browser_use.tools.views import ClickElementActionIndexOnly
from playwright.async_api import Error as PlaywrightError

from browser_use_camoufox import CamoufoxSession


async def get_node_by_id(session: CamoufoxSession, element_id: str):
	state_event = session.event_bus.dispatch(BrowserStateRequestEvent(include_dom=True, include_screenshot=False))
	await state_event
	state = await state_event.event_result()
	return next(node for node in state.dom_state.selector_map.values() if node.attributes.get('id') == element_id)


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
		assert diagnostics['action_plan']['strategy'] == 'direct_click'
		assert diagnostics['action_plan']['preconditions']['button'] == 'left'
		assert diagnostics['action_plan']['preconditions']['interactable'] is True
		assert diagnostics['action_plan']['attempted_steps'] == ['click']
		assert diagnostics['action_plan']['no_change_reason'] is None
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
		assert diagnostics['action_plan']['strategy'] == 'click_with_keyboard_recovery'
		assert diagnostics['action_plan']['attempted_steps'] == ['click', 'keyboard_activation']
		assert diagnostics['action_plan']['no_change_reason'] is None
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
		assert diagnostics['action_plan']['strategy'] == 'click_with_form_submit_recovery'
		assert diagnostics['action_plan']['attempted_steps'] == ['click', 'keyboard_activation', 'form_submit']
		assert diagnostics['action_plan']['no_change_reason'] is None
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_click_recovers_visible_autocomplete_option_after_no_change(tmp_path: Path):
	fixture = tmp_path / 'generic_autocomplete.html'
	fixture.write_text(
		"""
		<html>
			<head><title>Generic autocomplete</title></head>
			<body>
				<label for="destination">Destination</label>
				<input id="destination" role="combobox" aria-controls="suggestions" value="nor" />
				<ul id="suggestions" role="listbox">
					<li role="option" data-value="north">North Station</li>
					<li role="option" data-value="south">South Station</li>
				</ul>
				<p id="result">Waiting</p>
				<script>
					document.querySelectorAll('[role=option]').forEach((option) => {
						option.addEventListener('click', (event) => {
							if (option.dataset.value === 'north') {
								event.preventDefault();
								return;
							}
							document.querySelector('#result').textContent = `Selected ${option.textContent.trim()}`;
						});
					});
					document.querySelector('#destination').addEventListener('keydown', (event) => {
						if (event.key !== 'Enter') return;
						const options = Array.from(document.querySelectorAll('[role=option]'));
						const match = options.find((option) => option.dataset.value === 'north');
						document.querySelector('#result').textContent = `Selected ${match.textContent.trim()}`;
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
		option = next(
			node
			for node in state.dom_state.selector_map.values()
			if node.attributes.get('role') == 'option' and node.attributes.get('data-value') == 'north'
		)

		await session.on_ClickElementEvent(ClickElementEvent(node=option))

		page = await session.get_current_page()
		assert await page.locator('#result').text_content() == 'Selected North Station'
		diagnostics = session.last_click_diagnostics
		assert diagnostics is not None
		assert diagnostics['fallback']['attempted'] == ['click', 'autocomplete_option']
		assert diagnostics['fallback']['result'] == 'autocomplete_option_succeeded'
		assert diagnostics['action_plan']['strategy'] == 'click_with_autocomplete_recovery'
		assert diagnostics['action_plan']['attempted_steps'] == ['click', 'autocomplete_option']
		assert diagnostics['action_plan']['no_change_reason'] is None
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_click_rejects_ambiguous_autocomplete_option_recovery(tmp_path: Path):
	fixture = tmp_path / 'generic_ambiguous_autocomplete.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<input id="destination" role="combobox" aria-controls="suggestions" value="central" />
				<ul id="suggestions" role="listbox">
					<li role="option" data-value="central">Central Station</li>
					<li role="option" data-value="central">Central Station</li>
				</ul>
				<p id="result">Waiting</p>
				<script>
					document.querySelectorAll('[role=option]').forEach((option) => {
						option.addEventListener('click', (event) => event.preventDefault());
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
		option = next(node for node in state.dom_state.selector_map.values() if node.attributes.get('role') == 'option')

		with pytest.raises(RuntimeError, match='candidate_ranking'):
			await session.on_ClickElementEvent(ClickElementEvent(node=option))

		page = await session.get_current_page()
		assert await page.locator('#result').text_content() == 'Waiting'
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_state_includes_non_aria_autocomplete_suggestions(tmp_path: Path):
	fixture = tmp_path / 'custom_autocomplete.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<label for="location">Location</label>
				<input id="location" value="har" data-overlay="location-results" />
				<div id="location-results" class="suggestion-panel">
					<div class="suggestion" data-value="harbor">Harbor Center</div>
					<div class="suggestion" data-value="harvest">Harvest Square</div>
					<div class="suggestion" data-value="hidden" style="display:none">Hidden Place</div>
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

		suggestions = [
			node for node in state.dom_state.selector_map.values() if node.attributes.get('class') == 'suggestion'
		]
		assert [suggestion.node_value for suggestion in suggestions] == ['Harbor Center', 'Harvest Square']
		assert all(
			suggestion.snapshot_node is not None and suggestion.snapshot_node.is_clickable for suggestion in suggestions
		)
		assert 'Hidden Place' not in state.dom_state.llm_representation()
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_click_recovers_non_aria_autocomplete_suggestion_after_no_change(tmp_path: Path):
	fixture = tmp_path / 'generic_non_aria_autocomplete_select.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<label for="destination">Destination</label>
				<input id="destination" value="har" data-overlay="destination-suggestions" />
				<div id="destination-suggestions" class="suggestion-panel">
					<div class="suggestion" data-value="harbor">Harbor Center</div>
					<div class="suggestion" data-value="harvest">Harvest Square</div>
				</div>
				<p id="result">Waiting</p>
				<script>
					document.querySelectorAll('.suggestion').forEach((suggestion) => {
						suggestion.addEventListener('click', (event) => event.preventDefault());
					});
					document.querySelector('#destination').addEventListener('change', (event) => {
						const option = Array.from(document.querySelectorAll('.suggestion'))
							.find((suggestion) => suggestion.dataset.value === event.target.value);
						if (option) {
							document.querySelector('#result').textContent = `Selected ${option.textContent.trim()}`;
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
		state_event = session.event_bus.dispatch(BrowserStateRequestEvent(include_dom=True, include_screenshot=False))
		await state_event
		state = await state_event.event_result()
		suggestion = next(
			node
			for node in state.dom_state.selector_map.values()
			if node.node_value == 'Harbor Center' and node.attributes.get('data-value') == 'harbor'
		)

		await session.on_ClickElementEvent(ClickElementEvent(node=suggestion))

		page = await session.get_current_page()
		assert await page.locator('#destination').input_value() == 'harbor'
		assert await page.locator('#result').text_content() == 'Selected Harbor Center'
		diagnostics = session.last_click_diagnostics
		assert diagnostics is not None
		assert diagnostics['fallback']['attempted'] == ['click', 'autocomplete_option']
		assert diagnostics['fallback']['result'] == 'autocomplete_option_succeeded'
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_click_scrolls_offscreen_target_before_hit_target_validation(tmp_path: Path):
	fixture = tmp_path / 'offscreen-click.html'
	fixture.write_text(
		"""
		<html>
			<body style="height: 3400px">
				<div style="height: 2600px"></div>
				<button id="buy-now" onclick="document.body.dataset.clicked='true'">Buy now</button>
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
		button = next(node for node in state.dom_state.selector_map.values() if node.attributes.get('id') == 'buy-now')

		await session.on_ClickElementEvent(ClickElementEvent(node=button))

		page = await session.get_current_page()
		assert await page.locator('body').get_attribute('data-clicked') == 'true'
		assert await page.evaluate('() => window.scrollY') > 0
		diagnostics = session.last_click_diagnostics
		assert diagnostics is not None
		assert diagnostics['action_plan']['preconditions']['hit_target_validated'] is True
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_click_uses_no_wait_after_for_navigation_target(monkeypatch, tmp_path: Path):
	fixture = tmp_path / 'navigation-click.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<button id="search">Search</button>
			</body>
		</html>
		"""
	)
	session = CamoufoxSession(headless=True)

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())
		button = await get_node_by_id(session, 'search')
		original_locator_for_node = session._locator_for_node
		click_kwargs = {}

		class LocatorProxy:
			def __init__(self, locator):
				self._locator = locator

			async def click(self, **kwargs):
				click_kwargs.update(kwargs)
				raise PlaywrightError('synthetic click failure')

			def __getattr__(self, name):
				return getattr(self._locator, name)

		def locator_for_node(node):
			return LocatorProxy(original_locator_for_node(node))

		monkeypatch.setattr(session, '_locator_for_node', locator_for_node)

		with pytest.raises(RuntimeError, match='no_change_detected'):
			await session.on_ClickElementEvent(ClickElementEvent(node=button))

		assert click_kwargs['no_wait_after'] is True
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_click_action_reports_page_change_in_long_term_memory(tmp_path: Path):
	fixture = tmp_path / 'click-memory.html'
	target = tmp_path / 'results.html'
	fixture.write_text(
		"""
		<html>
			<head><title>Search form</title></head>
			<body>
				<button id="search" onclick="location.href = 'results.html'">Search</button>
			</body>
		</html>
		"""
	)
	target.write_text('<html><head><title>Results Page</title></head><body>Result content</body></html>')
	session = CamoufoxSession(headless=True)

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())
		button = await get_node_by_id(session, 'search')

		result = await session.click_action(ClickElementActionIndexOnly(index=button.node_id))

		assert result.error is None
		assert result.long_term_memory is not None
		assert 'Page changed to Results Page' in result.long_term_memory
		assert target.as_uri() in result.long_term_memory
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_top_layer_intercepted_click_fixture_preserves_blocked_target(tmp_path: Path):
	fixture = tmp_path / 'top_layer_intercept.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<button id="blocked" onclick="
					if (event.detail > 0) document.body.dataset.clicked='true'
				">Continue checkout</button>
				<div
					id="modal-backdrop"
					role="dialog"
					aria-label="Confirm before continuing"
					onclick="event.stopPropagation()"
					style="
						position:fixed; left:0; top:0; width:100vw; height:100vh;
						z-index:1000; background:rgba(0,0,0,.2); pointer-events:all
					"
				>
					<button id="close">Review details</button>
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
		button = next(node for node in state.dom_state.selector_map.values() if node.attributes.get('id') == 'blocked')

		with pytest.raises(RuntimeError, match='Camoufox click failed after 5000ms'):
			await session.on_ClickElementEvent(ClickElementEvent(node=button))

		page = await session.get_current_page()
		assert await page.locator('body').get_attribute('data-clicked') is None
		assert session.last_click_diagnostics is not None
		assert session.last_click_diagnostics['action_plan']['no_change_reason'] == 'click_blocked_by_top_layer'
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_top_layer_blocked_autocomplete_option_uses_safe_selection_recovery(tmp_path: Path):
	fixture = tmp_path / 'blocked-autocomplete.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<input id="destination" aria-controls="suggestions" value="Montevideo" />
				<ul id="suggestions" role="listbox">
					<li id="choice" role="option">Montevideo, Uruguay</li>
				</ul>
				<div
					id="promo"
					style="position:fixed; left:0; top:0; width:100vw; height:100vh; z-index:10"
				>Sign in, save money</div>
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
		option = next(node for node in state.dom_state.selector_map.values() if node.attributes.get('id') == 'choice')

		await session.on_ClickElementEvent(ClickElementEvent(node=option))

		page = await session.get_current_page()
		assert await page.locator('#destination').input_value() == 'Montevideo, Uruguay'
		diagnostics = session.last_click_diagnostics
		assert diagnostics is not None
		assert diagnostics['fallback']['attempted'] == ['click', 'autocomplete_option']
		assert diagnostics['fallback']['result'] == 'autocomplete_option_succeeded'
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_coordinate_click_rejects_mismatched_hit_target(tmp_path: Path):
	fixture = tmp_path / 'coordinate-hit-target.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<button id="blocked" onclick="document.body.dataset.clicked='blocked'">Blocked action</button>
				<div
					id="cover"
					style="position:fixed; left:0; top:0; width:200px; height:80px; z-index:10"
					onclick="document.body.dataset.clicked='cover'"
				></div>
			</body>
		</html>
		"""
	)
	session = CamoufoxSession(headless=True)

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())
		page = await session.get_current_page()
		rect = await page.locator('#blocked').bounding_box()
		assert rect is not None

		click_event = ClickCoordinateEvent(coordinate_x=int(rect['x'] + 8), coordinate_y=int(rect['y'] + 8))
		with pytest.raises(RuntimeError, match='hit target mismatch'):
			await session.on_ClickCoordinateEvent(click_event)

		assert await page.locator('body').get_attribute('data-clicked') is None
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_nested_scroll_container_scrolls_then_clicks_target(tmp_path: Path):
	fixture = tmp_path / 'nested-scroll-click.html'
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

		await session.on_ScrollEvent(ScrollEvent(direction='down', amount=500, node=button))
		await session.on_ClickElementEvent(ClickElementEvent(node=button))

		page = await session.get_current_page()
		assert await page.locator('#load-more').text_content() == 'Loaded more results'
		diagnostics = session.last_click_diagnostics
		assert diagnostics is not None
		assert diagnostics['action_plan']['preconditions']['hit_target_validated'] is True
	finally:
		await session.stop()
