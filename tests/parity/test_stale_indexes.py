from pathlib import Path

import pytest
from browser_use.browser.events import BrowserStateRequestEvent, ClickElementEvent
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


@pytest.mark.anyio
async def test_direct_click_relocalizes_stale_target_once(tmp_path: Path):
	fixture = tmp_path / 'relocalize.html'
	fixture.write_text(
		"""
		<html><body>
			<button class="choice">Other</button>
			<button class="choice">Target</button>
		</body></html>
		"""
	)
	session = CamoufoxSession(headless=True)

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())
		state_event = session.event_bus.dispatch(BrowserStateRequestEvent(include_dom=True, include_screenshot=False))
		await state_event
		state = await state_event.event_result()
		target = next(node for node in state.dom_state.selector_map.values() if node.node_value == 'Target')

		page = await session.get_current_page()
		await page.evaluate(
			"""() => {
				document.body.innerHTML = `
					<button class="choice">Target</button>
					<button class="choice">Other</button>
				`;
				document.querySelector('.choice').addEventListener(
					'click',
					event => event.target.setAttribute('data-clicked', 'true')
				);
			}"""
		)

		await session.on_ClickElementEvent(ClickElementEvent(node=target))

		assert await page.locator('.choice').first.get_attribute('data-clicked') == 'true'
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_direct_click_keeps_stale_target_identity_across_repeated_results(tmp_path: Path):
	fixture = tmp_path / 'repeated_results.html'
	fixture.write_text(
		"""
		<html><body>
			<section class="result-card">
				<h2>Alpha result</h2>
				<a class="result-link" href="#alpha">Open</a>
			</section>
			<section class="result-card">
				<h2>Beta result</h2>
				<a class="result-link" href="#beta">Open</a>
			</section>
		</body></html>
		"""
	)
	session = CamoufoxSession(headless=True)

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())
		state_event = session.event_bus.dispatch(BrowserStateRequestEvent(include_dom=True, include_screenshot=False))
		await state_event
		state = await state_event.event_result()
		target = next(
			node
			for node in state.dom_state.selector_map.values()
			if node.attributes.get('href') == '#beta' and node.node_value == 'Open'
		)

		page = await session.get_current_page()
		await page.evaluate(
			"""() => {
				document.body.innerHTML = `
					<section class="result-card">
						<h2>Gamma result</h2>
						<a class="result-link" href="#gamma">Open</a>
					</section>
					<section class="result-card">
						<h2>Beta result</h2>
						<a class="result-link" href="#beta">Open</a>
					</section>
					<section class="result-card">
						<h2>Alpha result</h2>
						<a class="result-link" href="#alpha">Open</a>
					</section>
				`;
				document.querySelectorAll('.result-link').forEach((link) => {
					link.addEventListener('click', (event) => {
						event.preventDefault();
						document.body.dataset.clickedHref = link.getAttribute('href');
					});
				});
			}"""
		)

		await session.on_ClickElementEvent(ClickElementEvent(node=target))

		assert await page.locator('body').get_attribute('data-clicked-href') == '#beta'
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_direct_click_reports_ambiguous_stale_repeated_results(tmp_path: Path):
	fixture = tmp_path / 'ambiguous_repeated_results.html'
	fixture.write_text(
		"""
		<html><body>
			<section class="result-card"><h2>First duplicate</h2><a class="result-link" href="#same">Open</a></section>
			<section class="result-card"><h2>Second duplicate</h2><a class="result-link" href="#same">Open</a></section>
		</body></html>
		"""
	)
	session = CamoufoxSession(headless=True)

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())
		state_event = session.event_bus.dispatch(BrowserStateRequestEvent(include_dom=True, include_screenshot=False))
		await state_event
		state = await state_event.event_result()
		target = next(node for node in state.dom_state.selector_map.values() if node.attributes.get('href') == '#same')

		page = await session.get_current_page()
		await page.evaluate(
			"""() => {
				document.body.innerHTML = `
					<section class="result-card">
						<h2>Fresh duplicate</h2><a class="result-link" href="#same">Open</a>
					</section>
					<section class="result-card">
						<h2>Fresh duplicate</h2><a class="result-link" href="#same">Open</a>
					</section>
				`;
			}"""
		)

		with pytest.raises(RuntimeError, match='Ambiguous stale element relocalization'):
			await session.on_ClickElementEvent(ClickElementEvent(node=target))
	finally:
		await session.stop()
