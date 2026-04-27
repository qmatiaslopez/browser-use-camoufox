import json
from pathlib import Path

import pytest
from browser_use.browser.events import LoadStorageStateEvent, SaveStorageStateEvent

from browser_use_camoufox import CamoufoxSession


@pytest.mark.anyio
async def test_storage_headers_init_scripts_permissions_dialogs_downloads_and_boundaries(tmp_path: Path):
	storage_path = tmp_path / 'state.json'
	download_dir = tmp_path / 'downloads'
	fixture = tmp_path / 'capabilities.html'
	download_file = tmp_path / 'payload.txt'
	download_file.write_text('download payload')
	fixture.write_text(
		f"""
		<html>
			<body>
				<script>document.cookie = 'flavor=mate; path=/';</script>
				<a id="download" download="payload.txt" href="{download_file.as_uri()}">download</a>
				<button id="dialog" onclick="alert('handled')">dialog</button>
			</body>
		</html>
		"""
	)
	session = CamoufoxSession(
		headless=True,
		downloads_path=download_dir,
		headers={'x-camoufox-test': 'enabled'},
		permissions=['geolocation'],
		geolocation={'latitude': -34.9, 'longitude': -56.2},
		init_scripts=["window.__camoufoxInit = 'ready'"],
	)

	try:
		await session.start()
		page = await session.get_current_page()
		await page.route('**/echo', lambda route: route.fulfill(body=route.request.headers.get('x-camoufox-test', '')))
		await session.navigate_to(fixture.as_uri())
		await page.evaluate("localStorage.setItem('capability', 'stored')")

		saved = await session.on_SaveStorageStateEvent(SaveStorageStateEvent(path=str(storage_path)))
		assert storage_path.is_file()
		assert saved.path == str(storage_path)
		assert saved.cookies_count >= 1
		assert saved.cookies_count + saved.origins_count >= 1

		assert await page.evaluate('window.__camoufoxInit') == 'ready'
		assert session.extra_http_headers()['x-camoufox-test'] == 'enabled'

		dialog_task = page.locator('#dialog').click()
		dialog = await session.wait_for_dialog(trigger=dialog_task)
		assert dialog.message == 'handled'
		assert await page.locator('#dialog').text_content() == 'dialog'

		download = await session.download_from('#download')
		assert download.file_name == 'payload.txt'
		assert Path(download.path).read_text() == 'download payload'

		boundaries = session.unsupported_capabilities()
		assert boundaries['captcha'] == 'unsupported_capability'
		assert boundaries['traces_dir'] == 'unsupported_profile_mapping'
	finally:
		await session.stop()

	stored_cookies = json.loads(storage_path.read_text())['cookies']
	assert stored_cookies
	storage_path.write_text(
		json.dumps(
			{'cookies': [{'name': 'restored', 'value': 'yes', 'domain': 'example.com', 'path': '/'}], 'origins': []}
		)
	)
	reloaded = CamoufoxSession(headless=True, storage_state=str(storage_path))
	try:
		await reloaded.start()
		await reloaded.navigate_to(fixture.as_uri())
		await reloaded.on_LoadStorageStateEvent(LoadStorageStateEvent(path=str(storage_path)))
		assert json.loads(storage_path.read_text())['cookies']
	finally:
		await reloaded.stop()
