import json

import pytest

from browser_use_camoufox.conformance import CONFORMANCE_OUTCOMES, build_current_matrix, run_conformance


def test_current_matrix_represents_local_parity_themes():
	matrix = build_current_matrix(fixtures_only=True)
	themes = {scenario.theme for scenario in matrix.scenarios}

	assert {
		'backend_lifecycle',
		'tools',
		'forms',
		'stale_indexes',
		'tabs',
		'frames',
		'storage',
		'screenshot',
		'pdf',
		'artifacts',
		'dom_shadow',
		'no_cdp_boundaries',
		'mcp',
	}.issubset(themes)
	assert all(scenario.fixtures_only for scenario in matrix.scenarios)
	assert {scenario.classification for scenario in matrix.scenarios} <= CONFORMANCE_OUTCOMES


def test_current_matrix_has_precise_inventory_aligned_scenarios():
	matrix = build_current_matrix(fixtures_only=True)
	scenarios = {scenario.name: scenario for scenario in matrix.scenarios}

	assert scenarios['viewport screenshot artifacts'].classification == 'pass'
	assert scenarios['PDF artifact capability'].classification == 'conditional_capability'
	assert scenarios['HAR recording context options'].classification == 'pass'
	assert scenarios['video recording context options'].classification == 'pass'
	assert scenarios['same-origin iframe DOM boundary'].classification == 'pass'
	assert scenarios['cross-origin iframe decision'].classification == 'pass'
	assert scenarios['open shadow DOM boundary'].classification == 'pass'
	assert scenarios['raw CDP access boundary'].classification == 'not_applicable_no_cdp'
	assert scenarios['captcha hooks boundary'].classification == 'not_applicable_no_cdp'
	assert scenarios['tracing profiling coverage boundary'].classification == 'not_applicable_no_cdp'


def test_passing_conformance_scenarios_have_executable_evidence():
	matrix = build_current_matrix(fixtures_only=True)

	for scenario in matrix.scenarios:
		if scenario.classification in {'pass', 'pass_with_recovery'}:
			assert scenario.evidence, scenario.name
			assert scenario.evidence.startswith('pytest:'), scenario.name
		if scenario.classification == 'not_applicable_no_cdp':
			assert scenario.boundary_check == 'no_fake_cdp', scenario.name


def test_public_site_scenarios_are_opt_in():
	fixtures_only = build_current_matrix(fixtures_only=True)
	with_public = build_current_matrix(fixtures_only=False, include_public=True)

	assert not any(scenario.public_site for scenario in fixtures_only.scenarios)
	assert any(scenario.public_site for scenario in with_public.scenarios)


@pytest.mark.anyio
async def test_conformance_runner_reports_classified_results():
	report = await run_conformance(matrix_name='current', fixtures_only=True)
	payload = json.loads(report.to_json())

	assert payload['matrix'] == 'current'
	assert payload['ok'] is True
	assert payload['summary']['total'] == len(payload['results'])
	assert payload['summary']['environmental_failure'] == 0
	assert {result['classification'] for result in payload['results']} <= CONFORMANCE_OUTCOMES
	assert all(result['details'] != 'Passed deterministic fixture conformance.' for result in payload['results'])
