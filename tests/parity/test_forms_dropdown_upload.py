from pathlib import Path

import pytest
from browser_use.browser.events import BrowserStateRequestEvent
from browser_use.filesystem.file_system import FileSystem
from browser_use.tools.service import Tools

from browser_use_camoufox import CamoufoxSession, register_camoufox_tools


@pytest.mark.anyio
async def test_dropdown_options_selection_and_upload_without_cdp(tmp_path: Path):
	fixture = tmp_path / 'form.html'
	upload = tmp_path / 'upload.txt'
	upload.write_text('upload payload')
	fixture.write_text(
		"""
		<html>
			<body>
				<select id="country">
					<option value="uy">Uruguay</option>
					<option value="br">Brazil</option>
				</select>
				<input id="upload" type="file" />
			</body>
		</html>
		"""
	)
	tools = Tools()
	register_camoufox_tools(tools)
	session = CamoufoxSession(headless=True)

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())
		state_event = session.event_bus.dispatch(BrowserStateRequestEvent(include_dom=True, include_screenshot=False))
		await state_event
		state = await state_event.event_result()
		select_index = next(
			index for index, node in state.dom_state.selector_map.items() if node.attributes.get('id') == 'country'
		)
		upload_index = next(
			index for index, node in state.dom_state.selector_map.items() if node.attributes.get('id') == 'upload'
		)

		options = await tools.registry.execute_action(
			'dropdown_options', {'index': select_index}, browser_session=session
		)
		selection = await tools.registry.execute_action(
			'select_dropdown', {'index': select_index, 'text': 'Brazil'}, browser_session=session
		)
		upload_result = await tools.registry.execute_action(
			'upload_file',
			{'index': upload_index, 'path': str(upload)},
			browser_session=session,
			available_file_paths=[str(upload)],
			file_system=FileSystem(tmp_path / 'files'),
		)

		page = await session.get_current_page()
		assert options.error is None
		assert 'Uruguay' in options.extracted_content
		assert 'Brazil' in options.extracted_content
		assert selection.error is None
		assert await page.locator('#country').input_value() == 'br'
		assert upload_result.error is None
		assert await page.locator('#upload').evaluate('element => element.files[0].name') == 'upload.txt'
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_dropdown_upload_and_stale_recovery_across_frames_and_shadow_dom(tmp_path: Path):
	fixture = tmp_path / 'advanced-form.html'
	frame_fixture = tmp_path / 'frame-form.html'
	upload = tmp_path / 'shadow-upload.txt'
	upload.write_text('shadow upload payload')
	frame_fixture.write_text(
		"""
		<html>
			<body>
				<select id="frame-country">
					<option value="uy">Uruguay</option>
					<option value="br">Brazil</option>
				</select>
			</body>
		</html>
		"""
	)
	fixture.write_text(
		f"""
		<html>
			<body>
				<select id="stale-country">
					<option value="old">Old</option>
				</select>
				<iframe src="{frame_fixture.as_uri()}"></iframe>
				<upload-host></upload-host>
				<script>
					const host = document.querySelector('upload-host');
					const root = host.attachShadow({{mode: 'open'}});
					root.innerHTML = '<input id="shadow-upload" type="file" />';
				</script>
			</body>
		</html>
		"""
	)
	tools = Tools()
	register_camoufox_tools(tools)
	session = CamoufoxSession(headless=True)

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())
		state_event = session.event_bus.dispatch(BrowserStateRequestEvent(include_dom=True, include_screenshot=False))
		await state_event
		state = await state_event.event_result()
		stale_index = next(
			index
			for index, node in state.dom_state.selector_map.items()
			if node.attributes.get('id') == 'stale-country'
		)
		frame_index = next(
			index
			for index, node in state.dom_state.selector_map.items()
			if node.attributes.get('id') == 'frame-country'
		)
		upload_index = next(
			index
			for index, node in state.dom_state.selector_map.items()
			if node.attributes.get('id') == 'shadow-upload'
		)

		page = await session.get_current_page()
		await page.evaluate(
			"""() => {
				document.querySelector('#stale-country').outerHTML = `
					<select id="fresh-country">
						<option value="ar">Argentina</option>
						<option value="cl">Chile</option>
					</select>`;
			}"""
		)

		stale_selection = await tools.registry.execute_action(
			'select_dropdown', {'index': stale_index, 'text': 'Chile'}, browser_session=session
		)
		frame_selection = await tools.registry.execute_action(
			'select_dropdown', {'index': frame_index, 'text': 'Brazil'}, browser_session=session
		)
		upload_result = await tools.registry.execute_action(
			'upload_file',
			{'index': upload_index, 'path': str(upload)},
			browser_session=session,
			available_file_paths=[str(upload)],
			file_system=FileSystem(tmp_path / 'files'),
		)

		assert stale_selection.error is None
		assert await page.locator('#fresh-country').input_value() == 'cl'
		assert frame_selection.error is None
		assert await page.frame(url=frame_fixture.as_uri()).locator('#frame-country').input_value() == 'br'
		assert upload_result.error is None
		shadow_upload_name = await page.locator('upload-host').evaluate(
			"host => host.shadowRoot.querySelector('#shadow-upload').files[0].name"
		)
		assert shadow_upload_name == 'shadow-upload.txt'
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_custom_dropdowns_are_inspectable_selectable_and_reject_non_dropdowns(tmp_path: Path):
	fixture = tmp_path / 'custom-dropdowns.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<div id="custom-country" role="listbox" aria-label="Country">
					<div role="option" data-value="uy">Uruguay</div>
					<div role="option" data-value="br">Brazil</div>
				</div>
				<button id="menu-button" aria-haspopup="menu" aria-expanded="false">Actions</button>
				<div id="actions-menu" role="menu">
					<button role="menuitem" data-value="archive">Archive</button>
					<button role="menuitem" data-value="delete">Delete</button>
				</div>
				<button id="not-dropdown">Plain text</button>
			</body>
		</html>
		"""
	)
	tools = Tools()
	register_camoufox_tools(tools)
	session = CamoufoxSession(headless=True)

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())
		state_event = session.event_bus.dispatch(BrowserStateRequestEvent(include_dom=True, include_screenshot=False))
		await state_event
		state = await state_event.event_result()
		listbox_index = next(
			index
			for index, node in state.dom_state.selector_map.items()
			if node.attributes.get('id') == 'custom-country'
		)
		menu_index = next(
			index for index, node in state.dom_state.selector_map.items() if node.attributes.get('id') == 'actions-menu'
		)
		non_dropdown_index = next(
			index for index, node in state.dom_state.selector_map.items() if node.attributes.get('id') == 'not-dropdown'
		)

		listbox_options = await tools.registry.execute_action(
			'dropdown_options', {'index': listbox_index}, browser_session=session
		)
		listbox_selection = await tools.registry.execute_action(
			'select_dropdown', {'index': listbox_index, 'text': 'Brazil'}, browser_session=session
		)
		menu_options = await tools.registry.execute_action(
			'dropdown_options', {'index': menu_index}, browser_session=session
		)
		menu_selection = await tools.registry.execute_action(
			'select_dropdown', {'index': menu_index, 'text': 'Delete'}, browser_session=session
		)
		non_dropdown = await tools.registry.execute_action(
			'dropdown_options', {'index': non_dropdown_index}, browser_session=session
		)

		page = await session.get_current_page()
		assert listbox_options.error is None
		assert 'Uruguay' in listbox_options.extracted_content
		assert 'Brazil' in listbox_options.extracted_content
		assert listbox_selection.error is None
		assert await page.locator('[role="option"][data-value="br"]').get_attribute('aria-selected') == 'true'
		assert menu_options.error is None
		assert 'Archive' in menu_options.extracted_content
		assert 'Delete' in menu_options.extracted_content
		assert menu_selection.error is None
		assert await page.locator('[role="menuitem"][data-value="delete"]').get_attribute('aria-selected') == 'true'
		assert non_dropdown.error is not None
		assert 'not a dropdown' in non_dropdown.error
	finally:
		await session.stop()
