import pytest
from browser_use.tools.service import Tools

from browser_use_camoufox import CamoufoxSession, register_camoufox_tools


def test_camoufox_tool_overrides_cover_cdp_dependent_browser_use_actions():
	tools = Tools()
	register_camoufox_tools(tools)

	actions = tools.registry.registry.actions
	for action_name in (
		'search_page',
		'find_elements',
		'evaluate',
		'scroll',
		'screenshot',
		'save_as_pdf',
		'dropdown_options',
		'select_dropdown',
		'upload_file',
	):
		action = actions[action_name]
		assert action.function.__module__ == 'browser_use_camoufox.session'


@pytest.mark.anyio
async def test_default_cdp_dependent_tool_fails_with_no_fake_cdp_guidance(tmp_path):
	fixture = tmp_path / 'tool-boundary.html'
	fixture.write_text('<html><body><p>CDP boundary</p></body></html>')
	session = CamoufoxSession(headless=True)
	tools = Tools()

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())
		with pytest.raises(RuntimeError, match='no fake CDP'):
			await tools.registry.execute_action(
				'evaluate', {'code': 'document.body.innerText'}, browser_session=session
			)
	finally:
		await session.stop()
