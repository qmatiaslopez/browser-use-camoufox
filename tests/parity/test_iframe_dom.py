import asyncio
import socket
import sys
from pathlib import Path

import pytest
from browser_use.browser.events import BrowserStateRequestEvent, ClickElementEvent, TypeTextEvent

from browser_use_camoufox import CamoufoxSession


def _free_port() -> int:
	with socket.socket() as sock:
		sock.bind(('127.0.0.1', 0))
		return int(sock.getsockname()[1])


async def _serve_directory(directory: Path, port: int):
	process = await asyncio.create_subprocess_exec(
		sys.executable,
		'-m',
		'http.server',
		str(port),
		'--bind',
		'127.0.0.1',
		'--directory',
		str(directory),
		stdout=asyncio.subprocess.DEVNULL,
		stderr=asyncio.subprocess.DEVNULL,
	)
	return process


@pytest.mark.anyio
async def test_same_origin_iframe_elements_are_visible_and_clickable(tmp_path: Path):
	iframe = tmp_path / 'iframe.html'
	iframe.write_text(
		"""
		<html>
			<body>
				<button id="frame-button" onclick="this.textContent = 'Clicked in frame'">Frame button</button>
				<input id="frame-input" />
			</body>
		</html>
		"""
	)
	fixture = tmp_path / 'page.html'
	fixture.write_text(
		f"""
		<html>
			<body>
				<iframe id="same-origin" src="{iframe.as_uri()}"></iframe>
			</body>
		</html>
		"""
	)
	session = CamoufoxSession(headless=True)

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())
		state_event = session.event_bus.dispatch(BrowserStateRequestEvent(include_dom=True, include_screenshot=False))
		await state_event
		state = await state_event.event_result()

		button = next(
			node for node in state.dom_state.selector_map.values() if node.attributes.get('id') == 'frame-button'
		)
		input_node = next(
			node for node in state.dom_state.selector_map.values() if node.attributes.get('id') == 'frame-input'
		)
		assert button.frame_id not in (None, 'main')
		assert (
			button.attributes['data-browser-use-camoufox-frame']
			== input_node.attributes['data-browser-use-camoufox-frame']
		)

		await session.event_bus.dispatch(ClickElementEvent(node=button))
		await session.event_bus.dispatch(TypeTextEvent(node=input_node, text='inside iframe'))

		page = await session.get_current_page()
		frame = page.frame(url=iframe.as_uri())
		assert frame is not None
		assert await frame.locator('#frame-button').text_content() == 'Clicked in frame'
		assert await frame.locator('#frame-input').input_value() == 'inside iframe'

		refreshed_event = session.event_bus.dispatch(
			BrowserStateRequestEvent(include_dom=True, include_screenshot=False)
		)
		await refreshed_event
		refreshed = await refreshed_event.event_result()
		refreshed_button = next(
			node for node in refreshed.dom_state.selector_map.values() if node.attributes.get('id') == 'frame-button'
		)
		assert refreshed_button.frame_id == button.frame_id
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_cross_origin_iframe_decision(tmp_path: Path):
	parent_dir = tmp_path / 'parent'
	child_dir = tmp_path / 'child'
	parent_dir.mkdir()
	child_dir.mkdir()
	parent_port = _free_port()
	child_port = _free_port()
	child_url = f'http://127.0.0.1:{child_port}/iframe.html'
	parent_url = f'http://127.0.0.1:{parent_port}/page.html'
	(child_dir / 'iframe.html').write_text(
		"""
		<html>
			<body>
				<button id="cross-frame-button" onclick="this.textContent = 'Clicked cross origin'">
					Cross frame button
				</button>
			</body>
		</html>
		"""
	)
	(parent_dir / 'page.html').write_text(
		f"""
		<html>
			<body>
				<iframe id="cross-origin-like" src="{child_url}"></iframe>
			</body>
		</html>
		"""
	)
	parent_server = await _serve_directory(parent_dir, parent_port)
	child_server = await _serve_directory(child_dir, child_port)
	session = CamoufoxSession(headless=True)

	try:
		await asyncio.sleep(0.25)
		await session.start()
		await session.navigate_to(parent_url)
		state_event = session.event_bus.dispatch(BrowserStateRequestEvent(include_dom=True, include_screenshot=False))
		await state_event
		state = await state_event.event_result()
		button = next(
			node for node in state.dom_state.selector_map.values() if node.attributes.get('id') == 'cross-frame-button'
		)

		assert button.frame_id not in (None, 'main')
		assert button.attributes['data-browser-use-camoufox-frame-url'] == child_url

		await session.event_bus.dispatch(ClickElementEvent(node=button))
		page = await session.get_current_page()
		frame = page.frame(url=child_url)
		assert frame is not None
		assert await frame.locator('#cross-frame-button').text_content() == 'Clicked cross origin'
	finally:
		await session.stop()
		parent_server.terminate()
		child_server.terminate()
		await parent_server.wait()
		await child_server.wait()


@pytest.mark.anyio
async def test_duplicate_iframe_urls_resolve_intended_frame(tmp_path: Path):
	iframe = tmp_path / 'duplicate.html'
	iframe.write_text(
		"""
		<html>
			<body>
				<button class="frame-button" onclick="this.textContent = `Clicked ${window.frameElement.id}`">
					Frame button
				</button>
			</body>
		</html>
		"""
	)
	fixture = tmp_path / 'page.html'
	fixture.write_text(
		f"""
		<html>
			<body>
				<iframe id="first-frame" src="{iframe.as_uri()}"></iframe>
				<iframe id="second-frame" src="{iframe.as_uri()}"></iframe>
			</body>
		</html>
		"""
	)
	session = CamoufoxSession(headless=True)

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())
		state_event = session.event_bus.dispatch(BrowserStateRequestEvent(include_dom=True, include_screenshot=False))
		await state_event
		state = await state_event.event_result()
		buttons = [
			node for node in state.dom_state.selector_map.values() if node.attributes.get('class') == 'frame-button'
		]

		assert len(buttons) == 2
		assert buttons[0].attributes['data-browser-use-camoufox-frame-url'] == iframe.as_uri()
		assert buttons[1].attributes['data-browser-use-camoufox-frame-url'] == iframe.as_uri()
		assert (
			buttons[0].attributes['data-browser-use-camoufox-frame']
			!= buttons[1].attributes['data-browser-use-camoufox-frame']
		)

		await session.event_bus.dispatch(ClickElementEvent(node=buttons[1]))
		page = await session.get_current_page()
		first_frame = page.frame(name='first-frame')
		second_frame = page.frame(name='second-frame')
		assert first_frame is not None
		assert second_frame is not None
		assert (await first_frame.locator('.frame-button').text_content()).strip() == 'Frame button'
		assert await second_frame.locator('.frame-button').text_content() == 'Clicked second-frame'
	finally:
		await session.stop()
