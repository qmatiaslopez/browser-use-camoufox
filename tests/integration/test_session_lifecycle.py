from pathlib import Path

import pytest

from browser_use_camoufox import CamoufoxSession


@pytest.mark.anyio
async def test_camoufox_session_lifecycle_navigation_and_screenshot(tmp_path: Path):
	fixture = tmp_path / 'page.html'
	fixture.write_text('<html><head><title>Camoufox smoke</title></head><body>Ready</body></html>')

	session = CamoufoxSession(headless=True)

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())

		assert await session.get_current_page_url() == fixture.as_uri()
		assert await session.get_current_page_title() == 'Camoufox smoke'
		assert await session.take_screenshot()
	finally:
		await session.stop()
