import json

from browser_use_camoufox.compat.surface_inventory import (
	INVENTORY_STATUSES,
	build_surface_inventory_report,
	format_surface_inventory_text,
)


def test_surface_inventory_maps_old_backend_surfaces_to_standalone_status():
	report = build_surface_inventory_report()
	surfaces = {surface.name: surface for surface in report.surfaces}

	assert {
		'context.har_recording',
		'context.video_recording',
		'dom.same_origin_iframes',
		'dom.open_shadow_roots',
		'artifacts.screenshot',
		'artifacts.pdf',
		'boundaries.raw_cdp',
		'boundaries.captcha',
		'boundaries.closed_shadow_roots',
		'boundaries.tracing_profiling_coverage',
		'tools.dropdown_upload',
		'mcp.session_helpers',
	}.issubset(surfaces)
	assert {surface.status for surface in report.surfaces} <= INVENTORY_STATUSES
	assert all(surface.old_backend_surface for surface in report.surfaces)
	assert all(surface.test_coverage for surface in report.surfaces)
	assert all(surface.evidence for surface in report.surfaces)
	assert all(surface.evidence.startswith('pytest:') for surface in report.surfaces)


def test_surface_inventory_cli_text_is_machine_parseable_json():
	report = build_surface_inventory_report()
	text = format_surface_inventory_text(report)
	payload = json.loads(text)

	assert payload['ok'] is True
	assert payload['summary'].get('missing', 0) == 0
	assert payload['surfaces'][0]['name']


def test_unsupported_profile_options_are_classified_with_no_cdp_guidance():
	report = build_surface_inventory_report()
	surfaces = {surface.name: surface for surface in report.surfaces}
	unsupported = surfaces['context.unsupported_profile_options']

	assert unsupported.status == 'not_applicable_no_cdp'
	assert 'rejected at construction' in unsupported.standalone_status
	assert 'silently forwarded' in unsupported.notes
