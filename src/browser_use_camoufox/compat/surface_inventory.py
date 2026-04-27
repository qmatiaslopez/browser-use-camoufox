import json
from collections import Counter
from dataclasses import asdict, dataclass

INVENTORY_STATUSES = {
	'migrated',
	'missing',
	'replaced',
	'not_applicable_no_cdp',
	'needs_decision',
}


@dataclass(frozen=True)
class SurfaceInventoryItem:
	name: str
	category: str
	old_backend_surface: str
	standalone_status: str
	status: str
	test_coverage: str
	evidence: str
	notes: str


@dataclass(frozen=True)
class SurfaceInventoryReport:
	surfaces: tuple[SurfaceInventoryItem, ...]

	@property
	def summary(self) -> dict[str, int]:
		counts = Counter(surface.status for surface in self.surfaces)
		return {
			'total': len(self.surfaces),
			**{status: counts.get(status, 0) for status in sorted(INVENTORY_STATUSES)},
		}

	@property
	def ok(self) -> bool:
		return self.summary['missing'] == 0 and self.summary['needs_decision'] == 0


def build_surface_inventory_report() -> SurfaceInventoryReport:
	return SurfaceInventoryReport(
		surfaces=(
			SurfaceInventoryItem(
				name='context.har_recording',
				category='context_options',
				old_backend_surface='record_har_path, record_har_content, record_har_mode context options',
				standalone_status='record_har_path, record_har_content, and record_har_mode passed to context creation',
				status='migrated',
				test_coverage='tests/parity/test_artifact_recording.py::test_camoufox_har_recording_options',
				evidence='pytest:tests/parity/test_artifact_recording.py::test_camoufox_har_recording_options',
				notes=(
					'Options are forwarded to Playwright context creation; runtime rejections include '
					'actionable HAR guidance.'
				),
			),
			SurfaceInventoryItem(
				name='context.video_recording',
				category='context_options',
				old_backend_surface='record_video_dir and record_video_size context options',
				standalone_status='record_video_dir and record_video_size passed to context creation',
				status='migrated',
				test_coverage='tests/parity/test_artifact_recording.py::test_camoufox_video_recording_options',
				evidence='pytest:tests/parity/test_artifact_recording.py::test_camoufox_video_recording_options',
				notes=(
					'Options are forwarded to Playwright context creation; artifacts are accepted when '
					'the runtime supports them and rejections include actionable video guidance.'
				),
			),
			SurfaceInventoryItem(
				name='context.storage_headers_scripts_permissions',
				category='context_options',
				old_backend_surface='storage state, extra headers, init scripts, permissions, downloads',
				standalone_status='implemented through BrowserContext options and post-context setup',
				status='migrated',
				test_coverage=(
					'tests/parity/test_browser_capabilities.py and tests/integration/test_session_lifecycle.py'
				),
				evidence='pytest:tests/parity/test_browser_capabilities.py tests/integration/test_session_lifecycle.py',
				notes='Storage state is normalized for Camoufox cookie requirements.',
			),
			SurfaceInventoryItem(
				name='context.unsupported_profile_options',
				category='context_options',
				old_backend_surface='traces_dir, proxy, disable_security, deterministic_rendering profile mappings',
				standalone_status='rejected at construction with per-option no-fake-CDP guidance',
				status='not_applicable_no_cdp',
				test_coverage='tests/integration/test_unsupported_boundaries.py',
				evidence='pytest:tests/integration/test_unsupported_boundaries.py',
				notes='Unsupported old profile mappings fail before launch instead of being silently forwarded.',
			),
			SurfaceInventoryItem(
				name='dom.stable_selectors',
				category='dom',
				old_backend_surface='stable selector candidates and ordinal metadata',
				standalone_status='selector map includes stable selector, ordinal, visibility, and disabled metadata',
				status='migrated',
				test_coverage=(
					'tests/integration/test_dom_selector_reliability.py and tests/parity/test_stale_indexes.py'
				),
				evidence='pytest:tests/integration/test_dom_selector_reliability.py tests/parity/test_stale_indexes.py',
				notes='Locator resolution uses selector metadata instead of the old tag.nth(node_id) fallback.',
			),
			SurfaceInventoryItem(
				name='dom.same_origin_iframes',
				category='dom',
				old_backend_surface='same-origin iframe DOM discovery and interaction',
				standalone_status='same-origin iframe elements are discovered and actions use Playwright frames',
				status='migrated',
				test_coverage='tests/parity/test_iframe_dom.py',
				evidence='pytest:tests/parity/test_iframe_dom.py',
				notes='Uses Playwright frame APIs without CDP target switching.',
			),
			SurfaceInventoryItem(
				name='dom.cross_origin_iframes',
				category='dom',
				old_backend_surface='cross-origin iframe target handling',
				standalone_status='cross-origin-like iframe elements are discovered and actions use Playwright frames',
				status='migrated',
				test_coverage='tests/parity/test_iframe_dom.py::test_cross_origin_iframe_decision',
				evidence='pytest:tests/parity/test_iframe_dom.py::test_cross_origin_iframe_decision',
				notes='Local separate-origin fixture verifies Playwright frame APIs without CDP target switching.',
			),
			SurfaceInventoryItem(
				name='dom.open_shadow_roots',
				category='dom',
				old_backend_surface='open shadow root DOM discovery',
				standalone_status='open shadow-root elements are discovered and actions use Playwright locators',
				status='migrated',
				test_coverage='tests/parity/test_shadow_dom.py',
				evidence='pytest:tests/parity/test_shadow_dom.py',
				notes='Closed shadow roots are explicitly classified as hosts without exposing inaccessible internals.',
			),
			SurfaceInventoryItem(
				name='events.navigation',
				category='events',
				old_backend_surface='navigate, back, forward, refresh, wait handlers',
				standalone_status='navigate, back, forward, refresh, and wait events implemented with Playwright APIs',
				status='migrated',
				test_coverage='tests/integration/test_agent_startup_navigation.py',
				evidence='pytest:tests/integration/test_agent_startup_navigation.py',
				notes='Wait behavior uses Playwright timeouts and does not depend on CDP lifecycle events.',
			),
			SurfaceInventoryItem(
				name='events.interactions',
				category='events',
				old_backend_surface='click, type, send keys, scroll, dropdown, upload',
				standalone_status='implemented for current selector model',
				status='migrated',
				test_coverage='tests/integration/test_basic_actions.py and tests/parity/test_forms_dropdown_upload.py',
				evidence='pytest:tests/integration/test_basic_actions.py tests/parity/test_forms_dropdown_upload.py',
				notes='Needs revalidation after selector, iframe, and shadow DOM migrations.',
			),
			SurfaceInventoryItem(
				name='tools.search_find_evaluate',
				category='tools',
				old_backend_surface='no-CDP search page, find elements, evaluate tool overrides',
				standalone_status='implemented with Playwright page APIs',
				status='migrated',
				test_coverage=(
					'tests/parity/test_search_extract_screenshot.py and tests/integration/test_tools_no_cdp.py'
				),
				evidence='pytest:tests/parity/test_search_extract_screenshot.py tests/integration/test_tools_no_cdp.py',
				notes='Avoids raw CDP sessions.',
			),
			SurfaceInventoryItem(
				name='tools.dropdown_upload',
				category='tools',
				old_backend_surface='dropdown options, select dropdown, upload file tool overrides',
				standalone_status='implemented for current selector model',
				status='migrated',
				test_coverage='tests/parity/test_forms_dropdown_upload.py',
				evidence='pytest:tests/parity/test_forms_dropdown_upload.py',
				notes='Needs revalidation after richer DOM model.',
			),
			SurfaceInventoryItem(
				name='mcp.session_helpers',
				category='mcp',
				old_backend_surface='HTML, screenshot, active session, tab helper compatibility',
				standalone_status='HTML and session listing patched; screenshot/tab helpers covered by session APIs',
				status='migrated',
				test_coverage='tests/integration/test_mcp_compat.py',
				evidence='pytest:tests/integration/test_mcp_compat.py',
				notes='Must continue avoiding cdp_client access for Camoufox sessions.',
			),
			SurfaceInventoryItem(
				name='artifacts.screenshot',
				category='artifacts',
				old_backend_surface='viewport and element screenshots',
				standalone_status='implemented for PNG screenshots',
				status='migrated',
				test_coverage='tests/parity/test_search_extract_screenshot.py',
				evidence='pytest:tests/parity/test_search_extract_screenshot.py',
				notes='Lossy quality formats are rejected actionably.',
			),
			SurfaceInventoryItem(
				name='artifacts.pdf',
				category='artifacts',
				old_backend_surface='save page as PDF',
				standalone_status='implemented when Playwright page.pdf is available',
				status='replaced',
				test_coverage='tests/parity/test_search_extract_screenshot.py',
				evidence='pytest:tests/parity/test_search_extract_screenshot.py',
				notes='Fails actionably if Camoufox runtime lacks PDF support.',
			),
			SurfaceInventoryItem(
				name='boundaries.raw_cdp',
				category='no_cdp_boundaries',
				old_backend_surface='cdp_client and raw CDP session access',
				standalone_status='intentionally unavailable',
				status='not_applicable_no_cdp',
				test_coverage='tests/integration/test_no_fake_cdp_boundaries.py',
				evidence='pytest:tests/integration/test_no_fake_cdp_boundaries.py',
				notes='Do not emulate CDP; callers need browser-use APIs or Playwright equivalents.',
			),
			SurfaceInventoryItem(
				name='boundaries.captcha',
				category='no_cdp_boundaries',
				old_backend_surface='captcha solving hooks',
				standalone_status='intentionally unavailable',
				status='not_applicable_no_cdp',
				test_coverage='tests/integration/test_no_fake_cdp_boundaries.py',
				evidence='pytest:tests/integration/test_no_fake_cdp_boundaries.py',
				notes='No fake CDP or third-party captcha bypass is provided.',
			),
			SurfaceInventoryItem(
				name='boundaries.closed_shadow_roots',
				category='no_cdp_boundaries',
				old_backend_surface='closed shadow root internals',
				standalone_status='intentionally not introspectable',
				status='not_applicable_no_cdp',
				test_coverage='tests/integration/test_no_fake_cdp_boundaries.py',
				evidence='pytest:tests/integration/test_no_fake_cdp_boundaries.py',
				notes='Closed shadow root hosts are classified, but inaccessible internals are not exposed.',
			),
			SurfaceInventoryItem(
				name='boundaries.tracing_profiling_coverage',
				category='no_cdp_boundaries',
				old_backend_surface='CDP tracing, profiling, and coverage domains',
				standalone_status='intentionally unavailable',
				status='not_applicable_no_cdp',
				test_coverage='tests/integration/test_no_fake_cdp_boundaries.py',
				evidence='pytest:tests/integration/test_no_fake_cdp_boundaries.py',
				notes='Use Playwright-supported tracing only if a future task adds it explicitly.',
			),
		)
	)


def format_surface_inventory_text(report: SurfaceInventoryReport) -> str:
	return json.dumps(
		{
			'ok': report.ok,
			'summary': report.summary,
			'surfaces': [asdict(surface) for surface in report.surfaces],
		},
		indent=2,
	)
