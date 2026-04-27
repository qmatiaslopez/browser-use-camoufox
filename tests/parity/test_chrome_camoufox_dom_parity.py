import importlib.util
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from browser_use.browser import BrowserSession
from browser_use.browser.events import BrowserStateRequestEvent, ClickElementEvent
from browser_use.dom.views import DOMSelectorMap

from browser_use_camoufox import CamoufoxSession

REAL_WORLD_KIT_PATH = Path(__file__).resolve().parents[2] / 'scripts' / 'real_world_kit.py'
REAL_WORLD_KIT_SPEC = importlib.util.spec_from_file_location('real_world_kit', REAL_WORLD_KIT_PATH)
assert REAL_WORLD_KIT_SPEC is not None
real_world_kit = importlib.util.module_from_spec(REAL_WORLD_KIT_SPEC)
assert REAL_WORLD_KIT_SPEC.loader is not None
REAL_WORLD_KIT_SPEC.loader.exec_module(real_world_kit)

CHROME_EXECUTABLE = Path.home() / '.cache/ms-playwright/chromium-1217/chrome-linux64/chrome'
CHROME_TEST_ARGS = [
	'--password-store=basic',
	'--use-mock-keychain',
	'--disable-save-password-bubble',
	'--disable-features=PasswordManagerOnboarding,PasswordLeakDetection,AutofillServerCommunication',
]
GENERIC_CONTRACT_HTML = """
<html>
	<body>
		<main>
			<h1>Dashboard summary</h1>
			<p class="status" data-state="ready" data-priority="high" aria-label="Ready status">
				System ready
			</p>
			<div role="gridcell" aria-selected="true" data-value="42">Cell value</div>
			<label><input id="enabled" type="checkbox" aria-checked="true" /> Enabled</label>
			<button id="open" aria-expanded="false" onclick="this.textContent = 'Opened details'">Open details</button>
			<button id="disabled" disabled aria-disabled="true">Disabled action</button>
			<p id="hidden" style="display: none">Hidden text</p>
		</main>
	</body>
</html>
"""


@contextmanager
def serve_directory(directory: Path) -> Iterator[str]:
	server = ThreadingHTTPServer(
		('127.0.0.1', 0),
		partial(SimpleHTTPRequestHandler, directory=str(directory)),
	)
	thread = threading.Thread(target=server.serve_forever, daemon=True)
	thread.start()
	try:
		yield f'http://127.0.0.1:{server.server_port}'
	finally:
		server.shutdown()
		thread.join()
		server.server_close()


def text_matches(llm_text: str, expected: list[str], unexpected: list[str]) -> dict[str, Any]:
	return {
		'present': [text for text in expected if text in llm_text],
		'missing': [text for text in expected if text not in llm_text],
		'unexpected_present': [text for text in unexpected if text in llm_text],
	}


def capture_attributes(selector_map: DOMSelectorMap) -> dict[str, str]:
	captured: dict[str, str] = {}
	for node in selector_map.values():
		for name in ('aria-checked', 'aria-disabled', 'aria-expanded', 'aria-selected', 'data-state', 'data-value'):
			if name in node.attributes:
				captured[name] = node.attributes[name]
	return captured


async def capture_session_contract(session: BrowserSession | CamoufoxSession, url: str) -> dict[str, Any]:
	try:
		await session.start()
		await session.navigate_to(url)
		state_event = session.event_bus.dispatch(BrowserStateRequestEvent(include_dom=True, include_screenshot=False))
		await state_event
		state = await state_event.event_result(raise_if_any=True)
		llm_text = state.dom_state.llm_representation()
		selector_map = state.dom_state.selector_map
		clickable_nodes = [
			node for node in selector_map.values() if node.snapshot_node and node.snapshot_node.is_clickable
		]
		observable_nodes = [
			node
			for node in selector_map.values()
			if node.attributes.get('data-browser-use-camoufox-observable') == 'true'
			or (node.snapshot_node and node.snapshot_node.is_clickable is False)
		]
		open_node = next((node for node in selector_map.values() if node.attributes.get('id') == 'open'), None)
		action_results: list[dict[str, Any]] = []
		if open_node is not None:
			try:
				if isinstance(session, CamoufoxSession):
					await session.on_ClickElementEvent(ClickElementEvent(node=open_node))
				else:
					page = await session.get_current_page()
					await page.evaluate("() => document.querySelector('#open').click()")
				action_results.append({'action': 'click-open', 'passed': True, 'summary': 'opened'})
			except Exception as exc:
				action_results.append({'action': 'click-open', 'passed': False, 'summary': str(exc)})
		return {
			'visible_text': text_matches(
				llm_text,
				['Dashboard summary', 'System ready', 'Cell value', 'Open details', 'Disabled action'],
				['Hidden text'],
			),
			'attributes': capture_attributes(selector_map),
			'actionable_count': len(clickable_nodes),
			'observable_only_count': len(observable_nodes),
			'action_results': action_results,
			'llm_text': llm_text,
		}
	finally:
		await session.stop()


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
		disabled = next(
			node for node in state.dom_state.selector_map.values() if node.attributes.get('aria-disabled') == 'true'
		)
		assert disabled.attributes['data-browser-use-camoufox-disabled'] == 'true'
		assert disabled.attributes['data-browser-use-camoufox-observable'] == 'true'
		assert disabled.snapshot_node is not None
		assert disabled.snapshot_node.is_clickable is False
		assert any(node.attributes.get('id') == 'open' for node in clickable)
		assert not any(node.attributes.get('id') == 'hidden' for node in state.dom_state.selector_map.values())
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_chrome_camoufox_generic_fixture_parity_matrix_uses_real_browser_capture(tmp_path: Path):
	if not CHROME_EXECUTABLE.exists():
		pytest.skip(f'Chrome executable not found: {CHROME_EXECUTABLE}')
	fixture = tmp_path / 'generic-dom-contract.html'
	fixture.write_text(GENERIC_CONTRACT_HTML)

	with serve_directory(tmp_path) as base_url:
		url = f'{base_url}/{fixture.name}'
		chrome = await capture_session_contract(
			BrowserSession(
				headless=True,
				executable_path=CHROME_EXECUTABLE,
				args=CHROME_TEST_ARGS,
				enable_default_extensions=False,
				keep_alive=False,
			),
			url,
		)
		camoufox = await capture_session_contract(CamoufoxSession(headless=True), url)

	assert chrome['visible_text']['unexpected_present'] == []
	assert camoufox['visible_text']['unexpected_present'] == []
	assert chrome['action_results'] and all(result['passed'] for result in chrome['action_results'])
	assert camoufox['action_results'] and all(result['passed'] for result in camoufox['action_results'])

	rows = [
		{'runtime': 'chrome', 'fixture': 'generic-dom-contract', **chrome},
		{'runtime': 'camoufox', 'fixture': 'generic-dom-contract', **camoufox},
	]
	report = real_world_kit.build_parity_matrix_report(rows)
	runtime_report = report['fixtures'][0]['runtimes']['camoufox']

	assert camoufox['visible_text']['missing'] == []
	assert runtime_report['visible_text_parity'] is True
	assert runtime_report['action_result_summary'] == [{'action': 'click-open', 'passed': True}]
	assert 'Hidden text' not in report['json']


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


def test_mission_report_diagnostics_classify_runtime_tooling_failure():
	report = real_world_kit.enrich_mission_report(
		{
			'passed': False,
			'errors': ['RuntimeError: Tool click failed because target detached'],
			'history': {
				'action_names': ['navigate', 'click_element', 'extract_content'],
				'urls': ['https://example.test/start', 'https://example.test/details'],
				'errors': ['ClickElementError: target detached'],
			},
			'verification': {'passed': False, 'details': {'url': 'https://example.test/details'}, 'errors': []},
		},
		final_state={
			'url': 'https://example.test/details',
			'title': 'Details',
			'body_text': 'Details page loaded with account_id=12345 and token abcdef',
			'dom_metrics': {'element_count': 7, 'body_text_length': 54},
		},
		duration_seconds=1.25,
	)

	assert report['diagnostics']['final_state']['url'] == 'https://example.test/details'
	assert report['diagnostics']['final_state']['title'] == 'Details'
	assert report['diagnostics']['final_state']['body_excerpt']
	assert report['diagnostics']['actions'] == {
		'names': ['navigate', 'click_element', 'extract_content'],
		'count': 3,
	}
	assert report['diagnostics']['duration_seconds'] == 1.25
	assert report['diagnostics']['url_transitions'] == [
		{'from': 'https://example.test/start', 'to': 'https://example.test/details'}
	]
	assert report['diagnostics']['runtime_tool_errors'] == ['ClickElementError: target detached']
	assert report['failure_class'] == 'runtime/tooling'
	assert 'abcdef' not in report['diagnostics']['final_state']['body_excerpt']


def test_benchmark_stack_has_five_families_three_variations_and_real_sites():
	missions = real_world_kit.MISSIONS
	assert len(missions) == 15

	by_family: dict[str, list[object]] = {}
	for mission in missions.values():
		by_family.setdefault(mission.family, []).append(mission)

	assert sorted(by_family) == [
		'Documentation lookup',
		'Dynamic keyboard app',
		'Knowledge navigation',
		'Public code/repo research',
		'Real public search/filter flows',
	]
	for family_missions in by_family.values():
		assert sorted(mission.variation for mission in family_missions) == [1, 2, 3]

	assert 'saucedemo' not in missions
	for mission in missions.values():
		assert mission.domains
		assert 'saucedemo' not in mission.url.lower()
		assert 'localhost' not in mission.url.lower()


def test_benchmark_matrix_report_compares_chrome_and_camoufox_runs():
	chrome = {
		'mission': {
			'id': 'wiki_basic_lookup',
			'family': 'Knowledge navigation',
			'variation': 1,
			'complexity': 'Simple',
		},
		'runtime': 'chrome',
		'passed': True,
		'failure_class': 'unknown',
		'history': {'is_successful': True, 'steps': 3},
		'verification': {'passed': True, 'errors': []},
		'diagnostics': {
			'duration_seconds': 10.0,
			'actions': {'count': 4},
			'final_state': {'url': 'https://en.wikipedia.org/wiki/Playwright_(software)', 'title': 'Playwright'},
		},
		'errors': [],
	}
	camoufox = {
		**chrome,
		'runtime': 'camoufox',
		'diagnostics': {
			'duration_seconds': 12.5,
			'actions': {'count': 5},
			'final_state': {'url': 'https://en.wikipedia.org/wiki/Playwright_(software)', 'title': 'Playwright'},
		},
	}

	report = real_world_kit.build_benchmark_matrix_report([chrome, camoufox])

	assert report['kind'] == 'real_world_chrome_cdp_camoufox_benchmark_matrix'
	assert report['summary']['total_runs'] == 2
	assert report['summary']['by_runtime']['chrome'] == {'runs': 1, 'passed': 1, 'failed': 0}
	assert report['summary']['by_runtime']['camoufox'] == {'runs': 1, 'passed': 1, 'failed': 0}
	assert report['missions'][0]['delta'] == {
		'pass_match': True,
		'failure_class_match': True,
		'duration_delta_seconds': 2.5,
		'step_delta': 0,
		'action_delta': 1,
		'chrome_passed': True,
		'camoufox_passed': True,
	}


def test_benchmark_matrix_report_preserves_runtime_candidate_diagnostics():
	report = real_world_kit.build_benchmark_matrix_report(
		[
			{
				'mission': {'id': 'generic_flow', 'family': 'Diagnostics', 'variation': 1, 'complexity': 'Medium'},
				'runtime': 'camoufox',
				'passed': False,
				'failure_class': 'runtime/tooling',
				'history': {'is_successful': False, 'steps': 2},
				'verification': {'passed': False, 'errors': []},
				'diagnostics': {
					'duration_seconds': 3.0,
					'actions': {'count': 2},
					'runtime_tool_errors': [
						'candidate_ranking=[node=1 score=20 semantic_evidence=Open password=super-secret-token]'
					],
					'fallback_paths': [{'action': 'click', 'path': ['locator'], 'result': 'ambiguous'}],
					'candidate_rankings': [{'node': 1, 'score': 20, 'semantic_evidence': 'Open'}],
				},
				'errors': ['timeout'],
			}
		]
	)

	runtime = report['missions'][0]['runtimes']['camoufox']
	assert runtime['failure_class'] == 'runtime/tooling'
	assert runtime['runtime_tool_errors']
	assert runtime['fallback_paths'] == [{'action': 'click', 'path': ['locator'], 'result': 'ambiguous'}]
	assert runtime['candidate_rankings'] == [{'node': 1, 'score': 20, 'semantic_evidence': 'Open'}]
	assert 'super-secret-token' not in report['json']


def test_benchmark_matrix_report_summarizes_owner_categories_and_all_missions():
	reports = []
	for mission in real_world_kit.MISSIONS.values():
		reports.append(
			{
				'mission': {
					'id': mission.id,
					'family': mission.family,
					'variation': mission.variation,
					'complexity': mission.complexity,
				},
				'runtime': 'camoufox',
				'passed': mission.id != 'mdn_fetch_lookup',
				'failure_class': 'unknown' if mission.id != 'mdn_fetch_lookup' else 'verifier weakness',
				'history': {'is_successful': True, 'steps': 2},
				'verification': {'passed': mission.id != 'mdn_fetch_lookup', 'errors': ['verifier token=secret']},
				'diagnostics': {
					'duration_seconds': 1.0,
					'actions': {'count': 2},
					'fallback_paths': [{'path': ['click'], 'result': 'succeeded'}],
					'candidate_rankings': [{'node': 7, 'score': 11, 'semantic_evidence': 'Safe label'}],
				},
				'errors': [],
			}
		)

	report = real_world_kit.build_benchmark_matrix_report(reports)

	assert report['summary']['mission_count'] == 15
	assert report['summary']['by_failure_class']['verifier weakness'] == 1
	assert report['summary']['by_owner_category'] == {
		'model': 0,
		'runtime': 0,
		'site': 0,
		'verifier': 1,
		'unknown': 14,
	}
	assert report['summary']['diagnostics'] == {
		'runtime_tool_error_runs': 0,
		'fallback_path_runs': 15,
		'candidate_ranking_runs': 15,
	}
	assert report['missions'][0]['runtimes']['camoufox']['owner_category'] in {
		'unknown',
		'verifier',
	}
	assert 'secret' not in report['json']
