from pathlib import Path

import pytest
from browser_use.browser.events import BrowserStateRequestEvent

from browser_use_camoufox import CamoufoxSession


@pytest.mark.anyio
async def test_generic_dom_observation_contract_exposes_visible_semantics(tmp_path: Path):
	fixture = tmp_path / 'generic-dom-contract.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<main>
					<h1>Dashboard summary</h1>
					<p class="status" data-state="ready" data-priority="high" aria-label="Ready status">
						System ready
					</p>
					<div role="gridcell" aria-selected="true" data-value="42">Cell value</div>
					<label><input id="enabled" type="checkbox" aria-checked="true" /> Enabled</label>
					<button id="open" aria-expanded="false">Open details</button>
					<button id="disabled" aria-disabled="true">Disabled action</button>
					<p id="hidden" style="display: none">Hidden text</p>
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
		assert 'Dashboard summary' in llm_text
		assert 'System ready' in llm_text
		assert 'Cell value' in llm_text
		assert 'data-state=ready' in llm_text
		assert 'aria-checked=true' in llm_text
		assert 'aria-expanded=false' in llm_text
		assert 'Hidden text' not in llm_text

		observable_only = [
			node
			for node in state.dom_state.selector_map.values()
			if node.attributes.get('data-browser-use-camoufox-observable') == 'true'
		]
		clickable = [
			node
			for node in state.dom_state.selector_map.values()
			if node.snapshot_node and node.snapshot_node.is_clickable
		]

		assert any(node.node_value == 'System ready' for node in observable_only)
		assert any(node.node_value == 'Cell value' for node in observable_only)
		assert any(node.attributes.get('data-priority') == 'high' for node in observable_only)
		assert any(node.attributes.get('aria-selected') == 'true' for node in observable_only)
		assert any(node.attributes.get('aria-disabled') == 'true' for node in clickable)
		assert any(node.attributes.get('id') == 'open' for node in clickable)
		assert not any(node.attributes.get('id') == 'hidden' for node in state.dom_state.selector_map.values())
	finally:
		await session.stop()
