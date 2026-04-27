import importlib.util
from pathlib import Path

import pytest
from browser_use.browser.events import BrowserStateRequestEvent

from browser_use_camoufox import CamoufoxSession

REAL_WORLD_KIT_PATH = Path(__file__).resolve().parents[2] / 'scripts' / 'real_world_kit.py'
REAL_WORLD_KIT_SPEC = importlib.util.spec_from_file_location('real_world_kit', REAL_WORLD_KIT_PATH)
assert REAL_WORLD_KIT_SPEC is not None
real_world_kit = importlib.util.module_from_spec(REAL_WORLD_KIT_SPEC)
assert REAL_WORLD_KIT_SPEC.loader is not None
REAL_WORLD_KIT_SPEC.loader.exec_module(real_world_kit)


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


def test_parity_matrix_report_summarizes_runtime_fixture_observation_and_actions():
	report = real_world_kit.build_parity_matrix_report(
		[
			{
				'runtime': 'chrome',
				'fixture': 'generic-dom-contract',
				'visible_text': ['Dashboard summary', 'System ready'],
				'attributes': {'data-token': 'super-secret-token', 'aria-selected': 'true'},
				'actionable_count': 2,
				'observable_only_count': 2,
				'action_results': [{'action': 'click', 'passed': True, 'summary': 'opened'}],
			},
			{
				'runtime': 'camoufox',
				'fixture': 'generic-dom-contract',
				'visible_text': ['Dashboard summary', 'System ready'],
				'attributes': {'data-token': 'super-secret-token', 'aria-selected': 'true'},
				'actionable_count': 2,
				'observable_only_count': 2,
				'action_results': [{'action': 'click', 'passed': True, 'summary': 'opened'}],
			},
		]
	)

	assert report['kind'] == 'chrome_camoufox_parity_matrix'
	assert report['fixtures'][0]['fixture'] == 'generic-dom-contract'
	assert report['fixtures'][0]['runtimes']['chrome']['visible_text_parity'] == 'baseline'
	assert report['fixtures'][0]['runtimes']['camoufox']['visible_text_parity'] is True
	assert report['fixtures'][0]['runtimes']['camoufox']['attribute_parity'] is True
	assert report['fixtures'][0]['runtimes']['camoufox']['actionable_count'] == 2
	assert report['fixtures'][0]['runtimes']['camoufox']['observable_only_count'] == 2
	assert report['fixtures'][0]['runtimes']['camoufox']['action_result_summary'] == [
		{'action': 'click', 'passed': True}
	]
	assert 'super-secret-token' not in report['json']


def test_scrub_redacts_sensitive_keys_and_tokens(monkeypatch):
	monkeypatch.setenv('CODEX_LB_API_KEY', 'api-secret')

	assert real_world_kit.scrub({'api_key': 'api-secret', 'data-token': 'super-secret-token', 'ok': 'ready'}) == {
		'api_key': '<redacted>',
		'data-token': '<redacted>',
		'ok': 'ready',
	}
