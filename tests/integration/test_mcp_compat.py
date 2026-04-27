import json
from pathlib import Path

import pytest
from browser_use.mcp.server import BrowserUseServer

from browser_use_camoufox import CamoufoxSession, apply_camoufox_mcp_compat


@pytest.mark.anyio
async def test_mcp_html_screenshot_sessions_and_tabs_work_without_cdp(tmp_path: Path):
	first = tmp_path / 'first.html'
	second = tmp_path / 'second.html'
	first.write_text(
		'<html><head><title>First MCP</title></head><body><main id="content">Camoufox MCP</main></body></html>'
	)
	second.write_text('<html><head><title>Second MCP</title></head><body>Second tab</body></html>')

	server = BrowserUseServer()
	session = CamoufoxSession(headless=True)
	apply_camoufox_mcp_compat()

	try:
		await session.start()
		await session.navigate_to(first.as_uri())
		server.browser_session = session
		server._track_session(session)

		html = await server._get_html('#content')
		meta_json, screenshot_b64 = await server._screenshot(full_page=False)
		sessions = json.loads(await server._list_sessions())

		await session.navigate_to(second.as_uri(), new_tab=True)
		tabs = json.loads(await server._list_tabs())
		assert [tab['tab_id'] for tab in tabs] == ['0000', '0001']
		switch_result = await server._switch_tab(tabs[0]['tab_id'])
		go_back_result = await server._go_back()
		close_result = await server._close_tab(tabs[1]['tab_id'])

		assert html == '<main id="content">Camoufox MCP</main>'
		assert json.loads(meta_json)['size_bytes'] > 0
		assert screenshot_b64
		assert sessions[0]['active'] is True
		assert sessions[0]['current_url'] == first.as_uri()
		assert [tab['title'] for tab in tabs] == ['First MCP', 'Second MCP']
		assert 'Switched to tab' in switch_result
		assert 'First MCP' in switch_result or first.as_uri() in switch_result
		assert go_back_result == 'Navigated back'
		assert 'Closed tab' in close_result
		assert len(await session.get_tabs()) == 1
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_mcp_session_listing_keeps_mixed_sessions_safe(tmp_path: Path):
	class NonCamoufoxSession:
		id = 'non-camoufox'

	fixture = tmp_path / 'mixed.html'
	fixture.write_text('<html><head><title>Mixed MCP</title></head><body>Mixed session</body></html>')

	server = BrowserUseServer()
	session = CamoufoxSession(headless=True)
	apply_camoufox_mcp_compat()

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())
		server._track_session(session)
		server.active_sessions[NonCamoufoxSession.id] = {
			'session': NonCamoufoxSession(),
			'created_at': server.active_sessions[session.id]['created_at'],
			'last_activity': server.active_sessions[session.id]['last_activity'],
			'url': 'about:blank',
		}

		sessions = json.loads(await server._list_sessions())

		by_id = {item['session_id']: item for item in sessions}
		assert by_id[session.id]['active'] is True
		assert by_id[session.id]['current_url'] == fixture.as_uri()
		assert by_id[NonCamoufoxSession.id]['active'] is False
		assert by_id[NonCamoufoxSession.id]['current_url'] == 'about:blank'
	finally:
		await session.stop()
