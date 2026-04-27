from pathlib import Path

import pytest
from browser_use.filesystem.file_system import FileSystem
from browser_use.tools.service import Tools

from browser_use_camoufox import CamoufoxSession, register_camoufox_tools


@pytest.mark.anyio
async def test_browser_use_tools_search_find_evaluate_screenshot_and_pdf_without_cdp(tmp_path: Path):
	fixture = tmp_path / 'tools.html'
	fixture.write_text(
		"""
		<html>
			<head><title>Tool surfaces</title></head>
			<body>
				<main id="content">
					<a class="result" href="https://example.com/ada">Ada Lovelace</a>
					<p>Camoufox direct evaluation works without CDP.</p>
				</main>
			</body>
		</html>
		"""
	)
	file_system = FileSystem(tmp_path / 'files')
	session = CamoufoxSession(headless=True)
	tools = Tools()
	register_camoufox_tools(tools)

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())

		search_result = await tools.registry.execute_action(
			'search_page', {'pattern': 'direct evaluation'}, browser_session=session
		)
		find_result = await tools.registry.execute_action(
			'find_elements',
			{'selector': 'a.result', 'attributes': ['href'], 'include_text': True},
			browser_session=session,
		)
		evaluate_result = await tools.registry.execute_action(
			'evaluate', {'code': "document.querySelector('a.result').textContent"}, browser_session=session
		)
		screenshot_result = await tools.registry.execute_action(
			'screenshot', {'file_name': 'tool-shot'}, browser_session=session, file_system=file_system
		)
		pdf_result = await tools.registry.execute_action(
			'save_as_pdf', {'file_name': 'tool-page'}, browser_session=session, file_system=file_system
		)

		assert search_result.error is None
		assert 'direct evaluation' in search_result.extracted_content
		assert find_result.error is None
		assert 'https://example.com/ada' in find_result.extracted_content
		assert evaluate_result.error is None
		assert evaluate_result.extracted_content == 'Ada Lovelace'
		assert screenshot_result.error is None
		assert (file_system.get_dir() / 'tool-shot.png').is_file()
		if pdf_result.error is None:
			assert (file_system.get_dir() / 'tool-page.pdf').is_file()
		else:
			assert 'PDF generation is unsupported' in pdf_result.error
	finally:
		await session.stop()
