from pathlib import Path

import pytest

from browser_use_camoufox import CamoufoxSession


@pytest.mark.anyio
async def test_camoufox_har_recording_options(tmp_path: Path):
	har_path = tmp_path / 'session.har'
	session = CamoufoxSession(
		headless=True,
		record_har_path=har_path,
		record_har_content='embed',
		record_har_mode='minimal',
	)

	options = session._playwright_context_options()

	assert options['record_har_path'] == str(har_path)
	assert options['record_har_content'] == 'embed'
	assert options['record_har_mode'] == 'minimal'

	fixture = tmp_path / 'page.html'
	fixture.write_text('<html><body>HAR fixture</body></html>')

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())
		await session.stop()
	except Exception as exc:
		message = str(exc)
		assert 'HAR recording options were rejected by the Camoufox runtime' in message
		assert 'record_har_path' in message
		await session.stop()

	if not session._recording_rejected:
		assert har_path.exists()
		assert har_path.stat().st_size > 0


@pytest.mark.anyio
async def test_camoufox_video_recording_options(tmp_path: Path):
	video_dir = tmp_path / 'videos'
	video_size = {'width': 320, 'height': 240}
	session = CamoufoxSession(
		headless=True,
		record_video_dir=video_dir,
		record_video_size=video_size,
	)

	options = session._playwright_context_options()

	assert options['record_video_dir'] == str(video_dir)
	assert options['record_video_size'] == video_size

	fixture = tmp_path / 'page.html'
	fixture.write_text('<html><body>Video fixture</body></html>')

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())
		await session.stop()
	except Exception as exc:
		message = str(exc)
		assert 'Video recording options were rejected by the Camoufox runtime' in message
		assert 'record_video_dir' in message
		await session.stop()

	if not session._recording_rejected:
		assert video_dir.exists()
		assert any(path.stat().st_size > 0 for path in video_dir.iterdir())
