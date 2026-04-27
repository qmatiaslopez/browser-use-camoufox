from browser_use_camoufox import CamoufoxSession


def test_unsupported_boundaries_are_explicit_without_cdp():
	boundaries = CamoufoxSession(headless=True).unsupported_capabilities()

	assert boundaries == {
		'captcha': 'unsupported_capability',
		'closed_shadow_roots': 'not_introspectable',
		'coverage': 'not_applicable_no_cdp',
		'deterministic_rendering': 'unsupported_profile_mapping',
		'disable_security': 'unsupported_profile_mapping',
		'profiling': 'not_applicable_no_cdp',
		'proxy': 'unsupported_profile_mapping',
		'traces_dir': 'unsupported_profile_mapping',
		'tracing': 'not_applicable_no_cdp',
	}


def test_unsupported_profile_mappings_fail_at_construction_with_guidance():
	for option in ('traces_dir', 'proxy', 'disable_security', 'deterministic_rendering'):
		try:
			CamoufoxSession(headless=True, **{option: 'value'})
		except ValueError as exc:
			message = str(exc)
			assert option in message
			assert 'CamoufoxSession does not silently accept unsupported profile mappings' in message
			assert 'no fake CDP' in message
		else:
			raise AssertionError(f'{option} should fail before launch')
