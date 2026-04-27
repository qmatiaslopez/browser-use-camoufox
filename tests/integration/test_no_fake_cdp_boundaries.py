import pytest

from browser_use_camoufox import CamoufoxSession


@pytest.mark.anyio
async def test_raw_cdp_boundaries_fail_with_actionable_no_fake_cdp_guidance():
	session = CamoufoxSession(headless=True)

	assert session.cdp_client is not None
	assert not session.cdp_client
	with pytest.raises(RuntimeError) as exc_info:
		await session.cdp_client.send.Runtime.evaluate(params={'expression': '1+1'})
	message = str(exc_info.value)
	assert 'no fake CDP' in message
	assert 'Playwright-backed browser-use APIs' in message

	for method_name in ('get_or_create_cdp_session', 'start_tracing', 'start_profiling', 'start_coverage'):
		method = getattr(session, method_name)
		with pytest.raises(RuntimeError) as exc_info:
			await method()
		message = str(exc_info.value)
		assert 'no fake CDP' in message
		assert 'Playwright-backed browser-use APIs' in message


def test_impossible_surfaces_are_classified_explicitly():
	boundaries = CamoufoxSession(headless=True).unsupported_capabilities()

	assert boundaries['captcha'] == 'unsupported_capability'
	assert boundaries['closed_shadow_roots'] == 'not_introspectable'
	assert boundaries['tracing'] == 'not_applicable_no_cdp'
	assert boundaries['profiling'] == 'not_applicable_no_cdp'
	assert boundaries['coverage'] == 'not_applicable_no_cdp'
