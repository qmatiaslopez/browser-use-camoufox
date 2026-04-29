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


@pytest.mark.anyio
async def test_get_current_page_tracks_latest_context_page(tmp_path: Path):
	first = tmp_path / 'first.html'
	first.write_text('<html><head><title>First</title></head><body>First page</body></html>')
	second = tmp_path / 'second.html'
	second.write_text('<html><head><title>Second</title></head><body>Second page</body></html>')
	session = CamoufoxSession(headless=True)

	try:
		await session.start()
		await session.navigate_to(first.as_uri())
		context = session._context
		assert context is not None
		page = await context.new_page()
		await page.goto(second.as_uri())

		current = await session.get_current_page()

		assert current.url == second.as_uri()
		assert await session.get_current_page_title() == 'Second'
	finally:
		await session.stop()
