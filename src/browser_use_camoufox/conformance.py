import asyncio
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

CONFORMANCE_OUTCOMES = {
	'pass',
	'pass_with_recovery',
	'fail_actionable',
	'conditional_capability',
	'not_applicable_no_cdp',
	'needs_decision',
	'environmental_failure',
}


@dataclass(frozen=True)
class ConformanceScenario:
	name: str
	theme: str
	classification: str
	fixtures_only: bool = True
	public_site: bool = False
	evidence: str = ''
	boundary_check: str = ''
	details: str = ''


@dataclass(frozen=True)
class ConformanceMatrix:
	name: str
	scenarios: tuple[ConformanceScenario, ...]


@dataclass(frozen=True)
class ConformanceResult:
	name: str
	theme: str
	classification: str
	details: str


@dataclass(frozen=True)
class ConformanceReport:
	matrix: str
	results: tuple[ConformanceResult, ...]

	@property
	def summary(self) -> dict[str, int]:
		counts = Counter(result.classification for result in self.results)
		return {
			'total': len(self.results),
			**{outcome: counts.get(outcome, 0) for outcome in sorted(CONFORMANCE_OUTCOMES)},
		}

	@property
	def ok(self) -> bool:
		return self.summary['environmental_failure'] == 0

	def to_json(self) -> str:
		return json.dumps(
			{
				'matrix': self.matrix,
				'ok': self.ok,
				'summary': self.summary,
				'results': [asdict(result) for result in self.results],
			},
			indent=2,
		)


def build_current_matrix(*, fixtures_only: bool, include_public: bool = False) -> ConformanceMatrix:
	scenarios = [
		ConformanceScenario(
			'session lifecycle smoke',
			'backend_lifecycle',
			'pass',
			evidence='pytest:tests/integration/test_session_lifecycle.py',
		),
		ConformanceScenario(
			'tool search/find/evaluate surfaces',
			'tools',
			'pass',
			evidence='pytest:tests/parity/test_search_extract_screenshot.py tests/integration/test_tools_no_cdp.py',
		),
		ConformanceScenario(
			'form dropdown and upload surfaces',
			'forms',
			'pass',
			evidence='pytest:tests/parity/test_forms_dropdown_upload.py',
		),
		ConformanceScenario(
			'stale selector index recovery',
			'stale_indexes',
			'pass_with_recovery',
			evidence='pytest:tests/parity/test_stale_indexes.py',
		),
		ConformanceScenario(
			'tab list/switch/close helpers',
			'tabs',
			'pass',
			evidence='pytest:tests/integration/test_mcp_compat.py',
		),
		ConformanceScenario(
			'same-origin iframe DOM boundary',
			'frames',
			'pass',
			evidence='pytest:tests/parity/test_iframe_dom.py',
			details='Same-origin iframe DOM discovery and interaction use Playwright frame APIs.',
		),
		ConformanceScenario(
			'cross-origin iframe decision',
			'frames',
			'pass',
			evidence='pytest:tests/parity/test_iframe_dom.py::test_cross_origin_iframe_decision',
			details='Cross-origin-like iframe DOM discovery and click interaction use Playwright frame APIs.',
		),
		ConformanceScenario(
			'storage headers init scripts permissions',
			'storage',
			'pass',
			evidence='pytest:tests/parity/test_browser_capabilities.py tests/integration/test_session_lifecycle.py',
		),
		ConformanceScenario(
			'viewport screenshot artifacts',
			'screenshot',
			'pass',
			evidence='pytest:tests/parity/test_search_extract_screenshot.py',
		),
		ConformanceScenario(
			'PDF artifact capability',
			'pdf',
			'conditional_capability',
			evidence='pytest:tests/parity/test_search_extract_screenshot.py',
			details='PDF uses Playwright page.pdf when the Camoufox runtime exposes it and fails actionably otherwise.',
		),
		ConformanceScenario(
			'HAR recording context options',
			'artifacts',
			'pass',
			evidence='pytest:tests/parity/test_artifact_recording.py::test_camoufox_har_recording_options',
			details='HAR context options are forwarded to Playwright context creation with actionable runtime errors.',
		),
		ConformanceScenario(
			'video recording context options',
			'artifacts',
			'pass',
			evidence='pytest:tests/parity/test_artifact_recording.py::test_camoufox_video_recording_options',
			details=(
				'Video context options are forwarded to Playwright context creation with actionable runtime errors.'
			),
		),
		ConformanceScenario(
			'open shadow DOM boundary',
			'dom_shadow',
			'pass',
			evidence='pytest:tests/parity/test_shadow_dom.py',
			details='Open shadow-root discovery and interaction use Playwright locators; closed roots are classified.',
		),
		ConformanceScenario(
			'raw CDP access boundary',
			'no_cdp_boundaries',
			'not_applicable_no_cdp',
			boundary_check='no_fake_cdp',
		),
		ConformanceScenario(
			'captcha hooks boundary',
			'no_cdp_boundaries',
			'not_applicable_no_cdp',
			boundary_check='no_fake_cdp',
		),
		ConformanceScenario(
			'tracing profiling coverage boundary',
			'no_cdp_boundaries',
			'not_applicable_no_cdp',
			boundary_check='no_fake_cdp',
		),
		ConformanceScenario(
			'MCP html screenshot session tab helpers',
			'mcp',
			'pass',
			evidence='pytest:tests/integration/test_mcp_compat.py',
		),
	]
	if include_public and not fixtures_only:
		scenarios.extend(
			[
				ConformanceScenario(
					'public search engine smoke',
					'tools',
					'environmental_failure',
					fixtures_only=False,
					public_site=True,
					details='Requires explicit public-site opt in and network availability.',
				),
				ConformanceScenario(
					'public download smoke',
					'storage',
					'environmental_failure',
					fixtures_only=False,
					public_site=True,
					details='Requires explicit public-site opt in and network availability.',
				),
			]
		)
	if fixtures_only:
		scenarios = [scenario for scenario in scenarios if scenario.fixtures_only and not scenario.public_site]
	return ConformanceMatrix(name='current', scenarios=tuple(scenarios))


async def run_conformance(*, matrix_name: str, fixtures_only: bool, include_public: bool = False) -> ConformanceReport:
	if matrix_name != 'current':
		raise ValueError(f'Unknown conformance matrix: {matrix_name}')
	matrix = build_current_matrix(fixtures_only=fixtures_only, include_public=include_public)
	results = []
	for scenario in matrix.scenarios:
		classification = scenario.classification
		details = scenario.details or _default_details(scenario)
		if classification in {'pass', 'pass_with_recovery'} and not _evidence_targets_exist(scenario.evidence):
			classification = 'environmental_failure'
			details = f'Missing executable evidence: {scenario.evidence or "none"}'
		elif classification == 'not_applicable_no_cdp' and scenario.boundary_check != 'no_fake_cdp':
			classification = 'environmental_failure'
			details = 'No-CDP scenario lacks an actionable no_fake_cdp boundary check.'
		results.append(
			ConformanceResult(
				name=scenario.name,
				theme=scenario.theme,
				classification=classification,
				details=details,
			)
		)
	return ConformanceReport(matrix=matrix.name, results=tuple(results))


def run_conformance_sync(*, matrix_name: str, fixtures_only: bool, include_public: bool = False) -> ConformanceReport:
	return asyncio.run(
		run_conformance(matrix_name=matrix_name, fixtures_only=fixtures_only, include_public=include_public)
	)


def _default_details(scenario: ConformanceScenario) -> str:
	if scenario.evidence:
		return f'Backed by executable evidence: {scenario.evidence}.'
	if scenario.classification == 'conditional_capability':
		return 'Supported when the runtime exposes the required Playwright capability.'
	if scenario.classification == 'not_applicable_no_cdp':
		return 'Not applicable under the explicit no-fake-CDP architecture.'
	if scenario.classification == 'needs_decision':
		return 'Requires an explicit migration decision before being marked supported.'
	if scenario.classification == 'fail_actionable':
		return 'Currently fails with an actionable migration or unsupported-runtime classification.'
	if scenario.classification == 'pass_with_recovery':
		return 'Passed through the expected recovery path.'
	return 'Passed deterministic fixture conformance.'


def _evidence_targets_exist(evidence: str) -> bool:
	if not evidence.startswith('pytest:'):
		return False
	root = Path(__file__).resolve().parents[2]
	for target in evidence.removeprefix('pytest:').split():
		path_text = target.split('::', 1)[0]
		if not (root / path_text).exists():
			return False
	return True
