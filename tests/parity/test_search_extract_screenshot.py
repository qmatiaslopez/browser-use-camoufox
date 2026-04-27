from pathlib import Path

import pytest
from browser_use.filesystem.file_system import FileSystem
from browser_use.tools.service import Tools

from browser_use_camoufox import CamoufoxSession, register_camoufox_tools


@pytest.mark.anyio
async def test_search_find_screenshot_and_pdf_parity_surfaces(tmp_path: Path):
	fixture = tmp_path / 'parity.html'
	fixture.write_text(
		"""
		<html>
			<head><title>Parity surfaces</title></head>
			<body>
				<section id="products">
					<a class="item" href="/one">One</a>
					<a class="item" href="/two">Two</a>
				</section>
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

		search_result = await tools.registry.execute_action('search_page', {'pattern': 'One'}, browser_session=session)
		find_result = await tools.registry.execute_action(
			'find_elements', {'selector': 'a.item', 'attributes': ['href']}, browser_session=session
		)
		screenshot_result = await tools.registry.execute_action(
			'screenshot', {'file_name': 'parity'}, browser_session=session, file_system=file_system
		)
		pdf_result = await tools.registry.execute_action(
			'save_as_pdf', {'file_name': 'parity'}, browser_session=session, file_system=file_system
		)

		assert search_result.error is None
		assert 'One' in search_result.extracted_content
		assert find_result.error is None
		assert '/two' in find_result.extracted_content
		assert screenshot_result.error is None
		assert (file_system.get_dir() / 'parity.png').is_file()
		assert pdf_result.error is None or 'PDF generation is unsupported' in pdf_result.error
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_search_page_supports_regex_limits_context_and_scope_errors(tmp_path: Path):
	fixture = tmp_path / 'search.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<main id="content">
					<p>Alpha-100 first product marker.</p>
					<p>alpha-200 second product marker.</p>
					<p>ALPHA-300 third product marker.</p>
				</main>
				<aside>Alpha-999 ignored sidebar marker.</aside>
			</body>
		</html>
		"""
	)
	session = CamoufoxSession(headless=True)
	tools = Tools()
	register_camoufox_tools(tools)

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())

		regex_result = await tools.registry.execute_action(
			'search_page',
			{
				'pattern': r'alpha-\d+',
				'regex': True,
				'case_sensitive': False,
				'css_scope': '#content',
				'max_results': 2,
				'context_chars': 8,
			},
			browser_session=session,
		)
		case_result = await tools.registry.execute_action(
			'search_page',
			{
				'pattern': 'Alpha',
				'case_sensitive': True,
				'css_scope': '#content',
				'max_results': 5,
				'context_chars': 10,
			},
			browser_session=session,
		)
		missing_scope = await tools.registry.execute_action(
			'search_page', {'pattern': 'Alpha', 'css_scope': '#missing'}, browser_session=session
		)

		assert regex_result.error is None
		assert 'Found 3 matches' in regex_result.extracted_content
		assert '[1]' in regex_result.extracted_content
		assert '[2]' in regex_result.extracted_content
		assert '[3]' not in regex_result.extracted_content
		assert 'showing 2 of 3 total matches' in regex_result.extracted_content
		assert 'Alpha-999' not in regex_result.extracted_content
		assert 'in main#content > p' in regex_result.extracted_content
		assert case_result.error is None
		assert 'Found 1 match' in case_result.extracted_content
		assert 'Alpha-100' in case_result.extracted_content
		assert 'alpha-200' not in case_result.extracted_content
		assert missing_scope.error is not None
		assert 'CSS scope selector not found: #missing' in missing_scope.error
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_get_html_returns_selected_outer_html_without_cdp(tmp_path: Path):
	fixture = tmp_path / 'html.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<section id="details"><h1>Extract me</h1></section>
				<section id="other">Ignore me</section>
			</body>
		</html>
		"""
	)
	session = CamoufoxSession(headless=True)

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())

		html = await session.get_html('#details')

		assert '<section id="details">' in html
		assert '<h1>Extract me</h1>' in html
		assert 'Ignore me' not in html
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_find_elements_defaults_include_state_and_visible_text(tmp_path: Path):
	fixture = tmp_path / 'find-elements.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<div data-testid="state-card" data-state="present" aria-label="A present">
					<span>A</span>
					<span style="display: none">Hidden child</span>
				</div>
			</body>
		</html>
		"""
	)
	session = CamoufoxSession(headless=True)
	tools = Tools()
	register_camoufox_tools(tools)

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())

		result = await tools.registry.execute_action(
			'find_elements', {'selector': '[data-testid="state-card"]'}, browser_session=session
		)

		assert result.error is None
		assert 'data-state="present"' in result.extracted_content
		assert 'aria-label="A present"' in result.extracted_content
		assert '> A' in result.extracted_content
		assert 'Hidden child' not in result.extracted_content
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_search_and_find_share_visible_text_normalization_and_safe_attributes(tmp_path: Path):
	fixture = tmp_path / 'normalized-safe.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<main id="content">
					<div
						data-testid="safe-card"
						data-token="sample-value"
						data-description="Alpha   Beta"
						aria-label="Card label"
					>
						<span>Alpha</span>
						<span style="display: none">Hidden Secret</span>
						<span>Beta</span>
					</div>
				</main>
			</body>
		</html>
		"""
	)
	session = CamoufoxSession(headless=True)
	tools = Tools()
	register_camoufox_tools(tools)

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())

		search_result = await tools.registry.execute_action(
			'search_page',
			{'pattern': 'Alpha Beta', 'css_scope': '#content', 'context_chars': 12},
			browser_session=session,
		)
		find_result = await tools.registry.execute_action(
			'find_elements',
			{'selector': '[data-testid="safe-card"]', 'attributes': ['data-token', 'data-description']},
			browser_session=session,
		)

		assert search_result.error is None
		assert 'Found 1 match' in search_result.extracted_content
		assert 'Hidden Secret' not in search_result.extracted_content
		assert find_result.error is None
		assert '> Alpha Beta' in find_result.extracted_content
		assert 'Hidden Secret' not in find_result.extracted_content
		assert 'data-token' not in find_result.extracted_content
		assert 'data-description="Alpha Beta"' in find_result.extracted_content
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_search_and_find_include_bounded_element_evidence(tmp_path: Path):
	fixture = tmp_path / 'element-evidence.html'
	fixture.write_text(
		"""
		<html>
			<body>
				<main id="content">
					<section class="results">
						<a
							class="result primary"
							href="/safe-target"
							data-testid="search-card"
							data-session-token="must-not-leak"
						>
							Visible   Evidence
							<span style="visibility: hidden">Hidden Evidence</span>
						</a>
					</section>
				</main>
			</body>
		</html>
		"""
	)
	session = CamoufoxSession(headless=True)
	tools = Tools()
	register_camoufox_tools(tools)

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())

		search_result = await tools.registry.execute_action(
			'search_page',
			{'pattern': 'Visible Evidence', 'css_scope': '#content', 'context_chars': 8},
			browser_session=session,
		)
		find_result = await tools.registry.execute_action(
			'find_elements',
			{'selector': 'a.result', 'attributes': ['href', 'data-testid', 'data-session-token']},
			browser_session=session,
		)

		assert search_result.error is None
		assert 'section.results > a.result.primary' in search_result.extracted_content
		assert 'href="/safe-target"' in search_result.extracted_content
		assert 'data-testid="search-card"' in search_result.extracted_content
		assert 'Hidden Evidence' not in search_result.extracted_content
		assert 'data-session-token' not in search_result.extracted_content
		assert 'must-not-leak' not in search_result.extracted_content
		assert find_result.error is None
		assert 'section.results > a.result.primary' in find_result.extracted_content
		assert 'href="/safe-target"' in find_result.extracted_content
		assert 'data-testid="search-card"' in find_result.extracted_content
		assert '> Visible Evidence' in find_result.extracted_content
		assert 'Hidden Evidence' not in find_result.extracted_content
		assert 'data-session-token' not in find_result.extracted_content
		assert 'must-not-leak' not in find_result.extracted_content
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_evaluate_script_returns_json_for_structured_values(tmp_path: Path):
	fixture = tmp_path / 'evaluate.html'
	fixture.write_text('<html><body><p>Evaluate</p></body></html>')
	session = CamoufoxSession(headless=True)
	tools = Tools()
	register_camoufox_tools(tools)

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())

		result = await tools.registry.execute_action(
			'evaluate',
			{'code': '() => [{letter: "G", state: "correct"}, {letter: "L", state: "present"}]'},
			browser_session=session,
		)

		assert result.error is None
		assert result.extracted_content == '[{"letter": "G", "state": "correct"}, {"letter": "L", "state": "present"}]'
	finally:
		await session.stop()
