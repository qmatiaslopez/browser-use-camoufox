import argparse
import asyncio
import json
import os
import re
import time
import traceback
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from browser_use import Agent
from browser_use.browser import BrowserSession
from browser_use.llm.openai.chat import ChatOpenAI
from browser_use.tools.service import Tools
from playwright.async_api import Page

from browser_use_camoufox import CamoufoxSession, register_camoufox_tools

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = 'http://localhost:2455/v1'
DEFAULT_MODEL = 'gpt-5.4'
DEFAULT_CHROME_EXECUTABLE = Path.home() / '.cache/ms-playwright/chromium-1217/chrome-linux64/chrome'
CHROME_TEST_ARGS = [
	'--password-store=basic',
	'--use-mock-keychain',
	'--disable-save-password-bubble',
	'--disable-features=PasswordManagerOnboarding,PasswordLeakDetection,AutofillServerCommunication',
]
SENSITIVE_KEY_PARTS = ('api_key', 'apikey', 'authorization', 'cookie', 'password', 'secret', 'token')
SENSITIVE_TEXT_MARKERS = ('api_key', 'apikey', 'authorization', 'cookie', 'password', 'secret', 'token')
FAILURE_CLASSES = (
	'model/navigation',
	'runtime/tooling',
	'page availability',
	'challenge/interruption',
	'verifier weakness',
	'unknown',
)

MISSION_PRINCIPLES = """
Mandatory mission laws:
- Browser-use must control all browser actions through Agent.run().
- Use the configured browser runtime.
- Use the local OpenAI-compatible API with model gpt-5.4.
- Do not use hidden app state, page source, bundled JavaScript, internal JSON endpoints, or external answer sites.
- Do not claim success unless the visible browser state satisfies the mission success criteria.
- If the mission cannot be completed, finish with success=False and explain the observed blocker.
"""


@dataclass(frozen=True)
class Mission:
	id: str
	name: str
	url: str
	task: str
	success_criteria: str
	max_steps: int
	timeout_seconds: int
	family: str = ''
	variation: int = 0
	complexity: str = ''
	verifier: str = 'generic_visible'
	domains: tuple[str, ...] = ()
	visible_terms: tuple[str, ...] = ()
	final_terms: tuple[str, ...] = ()
	history_terms: tuple[str, ...] = ()
	requires_price: bool = False


@dataclass
class Verification:
	passed: bool
	details: dict[str, Any]
	errors: list[str]


MISSIONS = {
	'wiki_basic_lookup': Mission(
		id='wiki_basic_lookup',
		name='Wikipedia basic lookup',
		url='https://www.wikipedia.org/',
		task=(
			'Use Wikipedia search to open the article about Playwright, the software testing framework. '
			'Return the visible article title and one visible fact from the article. Finish with success=True only '
			'when the browser is on the Playwright Wikipedia article.'
		),
		success_criteria='The final page is a Wikipedia Playwright article and the final answer mentions Playwright.',
		max_steps=8,
		timeout_seconds=420,
		family='Knowledge navigation',
		variation=1,
		complexity='Simple',
		domains=('wikipedia.org',),
		visible_terms=('playwright',),
		final_terms=('playwright',),
	),
	'wiki_disambiguation_followup': Mission(
		id='wiki_disambiguation_followup',
		name='Wikipedia disambiguation follow-up',
		url='https://www.wikipedia.org/',
		task=(
			'Use Wikipedia to find the article for Playwright, the software testing framework, even if search or '
			'disambiguation results appear. Open the correct article and return two visible facts plus the final URL. '
			'Finish with success=True only after the correct article is visible.'
		),
		success_criteria='The final page is the Playwright software Wikipedia article with two visible facts reported.',
		max_steps=10,
		timeout_seconds=480,
		family='Knowledge navigation',
		variation=2,
		complexity='Medium',
		domains=('wikipedia.org',),
		visible_terms=('playwright',),
		final_terms=('playwright',),
	),
	'wiki_compare_articles': Mission(
		id='wiki_compare_articles',
		name='Wikipedia article comparison',
		url='https://www.wikipedia.org/',
		task=(
			'Use Wikipedia to inspect the Playwright software article and the Selenium software article. Compare them '
			'using only visible article content. Return two differences and include evidence that both article pages '
			'were visited. Finish with success=True only if both technologies are covered in the final answer.'
		),
		success_criteria='The final answer compares Playwright and Selenium using visible Wikipedia article content.',
		max_steps=14,
		timeout_seconds=600,
		family='Knowledge navigation',
		variation=3,
		complexity='Complex',
		domains=('wikipedia.org',),
		final_terms=('playwright', 'selenium'),
	),
	'github_repo_overview': Mission(
		id='github_repo_overview',
		name='GitHub repo overview',
		url='https://github.com/microsoft/playwright',
		task=(
			'Open the public GitHub repository microsoft/playwright. Extract the visible repository name, description, '
			'and one visible metadata item such as stars, forks, license, or latest release. Finish with success=True '
			'only while still on a GitHub page for microsoft/playwright.'
		),
		success_criteria=(
			'The final browser state is the microsoft/playwright GitHub repo and the answer summarizes it.'
		),
		max_steps=8,
		timeout_seconds=420,
		family='Public code/repo research',
		variation=1,
		complexity='Simple',
		domains=('github.com',),
		visible_terms=('playwright',),
		final_terms=('playwright',),
	),
	'github_docs_navigation': Mission(
		id='github_docs_navigation',
		name='GitHub docs navigation',
		url='https://github.com/microsoft/playwright',
		task=(
			'Use the GitHub UI for microsoft/playwright to find visible getting-started, docs, or installation '
			'content. '
			'Return one visible install/get-started command or documentation link text and where you found it. '
			'Finish with success=True only after visible repo documentation evidence is found.'
		),
		success_criteria='The final answer includes visible Playwright documentation or install evidence from GitHub.',
		max_steps=12,
		timeout_seconds=540,
		family='Public code/repo research',
		variation=2,
		complexity='Medium',
		domains=('github.com',),
		visible_terms=('playwright',),
		final_terms=('playwright',),
	),
	'github_issue_or_code_search': Mission(
		id='github_issue_or_code_search',
		name='GitHub issue or code search',
		url='https://github.com/microsoft/playwright',
		task=(
			'Use GitHub UI navigation or search within microsoft/playwright to find a visible issue, pull request, or '
			'code result related to trace viewer. Return the visible title/path, status if present, and one evidence '
			'line. Finish with success=True only when the final answer includes trace viewer evidence from GitHub.'
		),
		success_criteria='The final answer includes visible GitHub evidence related to Playwright trace viewer.',
		max_steps=16,
		timeout_seconds=720,
		family='Public code/repo research',
		variation=3,
		complexity='Complex',
		domains=('github.com',),
		final_terms=('trace', 'playwright'),
	),
	'mdn_fetch_lookup': Mission(
		id='mdn_fetch_lookup',
		name='MDN Fetch API lookup',
		url='https://developer.mozilla.org/',
		task=(
			'Use MDN Web Docs to find the Fetch API documentation. Return a concise visible syntax or usage fact. '
			'Finish with success=True only when the browser is on an MDN page about Fetch API.'
		),
		success_criteria='The final page is an MDN Fetch API page and the answer includes a visible Fetch API fact.',
		max_steps=8,
		timeout_seconds=420,
		family='Documentation lookup',
		variation=1,
		complexity='Simple',
		domains=('developer.mozilla.org',),
		visible_terms=('fetch',),
		final_terms=('fetch',),
	),
	'mdn_related_api_flow': Mission(
		id='mdn_related_api_flow',
		name='MDN related API flow',
		url='https://developer.mozilla.org/',
		task=(
			'Use MDN Web Docs to inspect Fetch API and AbortController documentation. Explain how AbortController '
			'relates to fetch requests using only visible docs. Finish with success=True only if both Fetch and '
			'AbortController are covered in the final answer.'
		),
		success_criteria='The final answer explains the visible MDN relationship between Fetch and AbortController.',
		max_steps=12,
		timeout_seconds=540,
		family='Documentation lookup',
		variation=2,
		complexity='Medium',
		domains=('developer.mozilla.org',),
		final_terms=('fetch', 'abortcontroller'),
	),
	'mdn_compatibility_research': Mission(
		id='mdn_compatibility_research',
		name='MDN compatibility research',
		url='https://developer.mozilla.org/',
		task=(
			'Use MDN Web Docs to find visible browser compatibility information for AbortController. Summarize support '
			'evidence for at least two browsers or a baseline/support statement. Finish with success=True only if the '
			'answer contains visible compatibility evidence.'
		),
		success_criteria='The final answer summarizes visible MDN compatibility evidence for AbortController.',
		max_steps=14,
		timeout_seconds=660,
		family='Documentation lookup',
		variation=3,
		complexity='Complex',
		domains=('developer.mozilla.org',),
		final_terms=('abortcontroller',),
	),
	'imdb_title_lookup': Mission(
		id='imdb_title_lookup',
		name='IMDb title lookup',
		url='https://www.imdb.com/',
		task=(
			'Use IMDb to search for the movie Inception. Open the title page and extract the visible title, year, and '
			'one visible rating or cast fact. Finish with success=True only on an IMDb page for Inception.'
		),
		success_criteria='The final browser state is an IMDb page for Inception and the answer includes visible facts.',
		max_steps=10,
		timeout_seconds=540,
		family='Real public search/filter flows',
		variation=1,
		complexity='Simple',
		domains=('imdb.com',),
		visible_terms=('inception',),
		final_terms=('inception',),
	),
	'ebay_product_filter': Mission(
		id='ebay_product_filter',
		name='eBay product filter',
		url='https://www.ebay.com/',
		task=(
			'Use eBay to search for wireless mouse. Apply one visible sort or filter such as Buy It Now, condition, or '
			'price sorting if available. Extract the first relevant visible listing title and price. Do not sign in or '
			'buy anything. Finish with success=True only when listing evidence is visible.'
		),
		success_criteria='The final answer includes a visible eBay listing title and price for wireless mouse.',
		max_steps=14,
		timeout_seconds=660,
		family='Real public search/filter flows',
		variation=2,
		complexity='Medium',
		domains=('ebay.',),
		final_terms=('mouse',),
		requires_price=True,
	),
	'booking_destination_search': Mission(
		id='booking_destination_search',
		name='Booking destination search',
		url='https://www.booking.com/',
		task=(
			'Use Booking.com to search for Montevideo, Uruguay for a future one-night stay for two adults. Handle only '
			'visible dialogs or filters. Extract one visible accommodation result with price or availability evidence. '
			'Do not sign in or reserve anything. Finish with success=True only when visible result evidence is found.'
		),
		success_criteria=(
			'The final answer includes one visible Booking.com Montevideo result with price or availability evidence.'
		),
		max_steps=18,
		timeout_seconds=840,
		family='Real public search/filter flows',
		variation=3,
		complexity='Complex',
		domains=('booking.com',),
		final_terms=('montevideo',),
	),
	'wordle_board_ready': Mission(
		id='wordle_board_ready',
		name='Wordle board ready',
		url='https://www.nytimes.com/games/wordle/index.html',
		task=(
			'Open Wordle. Close only visible welcome, help, subscription, or cookie dialogs if needed. Verify that the '
			'game board and on-screen keyboard are visible. Do not make a guess. Finish with success=True only when '
			'the visible board and keyboard are ready.'
		),
		success_criteria='The visible Wordle board and keyboard are present.',
		max_steps=8,
		timeout_seconds=420,
		family='Dynamic keyboard app',
		variation=1,
		complexity='Simple',
		verifier='wordle_board',
		domains=('nytimes.com',),
	),
	'wordle_one_guess_feedback': Mission(
		id='wordle_one_guess_feedback',
		name='Wordle one guess feedback',
		url='https://www.nytimes.com/games/wordle/index.html',
		task=(
			'Open Wordle, close visible dialogs if needed, submit exactly one valid starter guess using the visible '
			'board/keyboard, and report the visible tile feedback. Do not use hidden state, answer lists, or NYT JSON '
			'endpoints. Finish with success=True only after one complete submitted row has visible feedback.'
		),
		success_criteria='One Wordle row has five submitted letters with visible feedback states.',
		max_steps=10,
		timeout_seconds=540,
		family='Dynamic keyboard app',
		variation=2,
		complexity='Medium',
		verifier='wordle_feedback',
		domains=('nytimes.com',),
	),
	'wordle_solve_visible_feedback': Mission(
		id='wordle_solve_visible_feedback',
		name='Wordle daily solve from visible feedback',
		url='https://www.nytimes.com/games/wordle/index.html',
		task=(
			'Open Wordle and solve the daily puzzle only by playing guesses on the visible board. Close visible '
			'welcome or help modal if needed. Start with a valid five-letter English word, submit it, read the visible '
			'tile feedback, and choose the next guess from that feedback. Do not visit any other website, inspect '
			'source code, use NYT JSON endpoints, or use any known answer list. Finish with success=True only when a '
			'row is visibly all correct/green. If you cannot solve it in six guesses, finish with success=False and '
			'summarize every guess and the blocker.'
		),
		success_criteria='A submitted Wordle row is complete and every tile in that row is correct/green.',
		max_steps=18,
		timeout_seconds=900,
		family='Dynamic keyboard app',
		variation=3,
		complexity='Very complex',
		verifier='wordle_solved',
		domains=('nytimes.com',),
	),
}

DEFAULT_MISSION_IDS = tuple(MISSIONS)


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description='Run headed real-world browser-use-camoufox missions.')
	parser.add_argument('--mission', choices=sorted(MISSIONS), action='append', help='Mission id to run; repeatable.')
	parser.add_argument('--list-missions', action='store_true', help='List benchmark mission ids and exit.')
	parser.add_argument('--base-url', default=os.getenv('CODEX_LB_BASE_URL', DEFAULT_BASE_URL))
	parser.add_argument('--model', default=DEFAULT_MODEL)
	parser.add_argument('--runtime', choices=['camoufox', 'chrome'], default='camoufox')
	parser.add_argument('--chrome-executable', type=Path, default=DEFAULT_CHROME_EXECUTABLE)
	parser.add_argument('--headless', action='store_true', help='Run browser headless. Default is visible/headed.')
	parser.add_argument('--pause-after-task', type=float, default=3.0)
	parser.add_argument('--report-path', type=Path)
	return parser.parse_args()


def build_llm(*, model: str, base_url: str) -> ChatOpenAI:
	api_key = os.environ.get('CODEX_LB_API_KEY')
	if not api_key:
		raise RuntimeError('CODEX_LB_API_KEY is required and must not be written to files.')
	return ChatOpenAI(
		model=model,
		api_key=api_key,
		base_url=base_url,
		temperature=None,
		frequency_penalty=None,
		max_completion_tokens=4096,
		timeout=180,
	)


def build_tools(*, runtime: str) -> Tools:
	tools = Tools()
	if runtime == 'camoufox':
		register_camoufox_tools(tools)
	return tools


async def get_wordle_rows(session: CamoufoxSession | BrowserSession) -> tuple[str, list[list[dict[str, Any]]]]:
	page = await get_current_page(session)
	raw_tiles = await evaluate_page(
		page,
		"""() => Array.from(document.querySelectorAll('#wordle-app-game [data-testid="tile"]')).map(e => ({
			text: (e.textContent || '').toLowerCase(),
			state: e.getAttribute('data-state'),
			label: e.getAttribute('aria-label')
		}))""",
	)
	tiles = json.loads(raw_tiles) if isinstance(raw_tiles, str) else raw_tiles
	rows = [tiles[index : index + 5] for index in range(0, len(tiles), 5)]
	return await page_url(session, page), rows


async def verify_wordle_board(session: CamoufoxSession | BrowserSession) -> Verification:
	page = await get_current_page(session)
	raw_status = await evaluate_page(
		page,
		"""() => {
			const tileCount = document.querySelectorAll('#wordle-app-game [data-testid="tile"]').length;
			const keyCount = document.querySelectorAll('[data-testid="keyboard"] button, button[data-key]').length;
			const bodyText = document.body ? document.body.innerText : '';
			return {tileCount, keyCount, hasWordleText: /wordle/i.test(bodyText)};
		}""",
	)
	status = json.loads(raw_status) if isinstance(raw_status, str) else raw_status
	passed = status.get('tileCount', 0) >= 30 and (status.get('keyCount', 0) >= 20 or status.get('hasWordleText'))
	return Verification(
		passed=passed,
		details={'url': await page_url(session, page), **status},
		errors=[] if passed else ['Wordle board and keyboard were not visibly ready.'],
	)


async def verify_wordle_feedback(session: CamoufoxSession | BrowserSession) -> Verification:
	url, rows = await get_wordle_rows(session)
	feedback_rows = [
		row
		for row in rows
		if len(row) == 5
		and all(tile.get('text') for tile in row)
		and all(tile.get('state') and tile.get('state') != 'empty' for tile in row)
	]
	return Verification(
		passed=bool(feedback_rows),
		details={'url': url, 'feedback_rows': feedback_rows, 'rows': rows},
		errors=[] if feedback_rows else ['No complete Wordle row with visible feedback was found.'],
	)


async def verify_wordle_solved(session: CamoufoxSession | BrowserSession) -> Verification:
	url, rows = await get_wordle_rows(session)
	solved_rows = [
		''.join(tile['text'] for tile in row)
		for row in rows
		if len(row) == 5 and all(tile['text'] for tile in row) and all(tile['state'] == 'correct' for tile in row)
	]
	return Verification(
		passed=bool(solved_rows),
		details={'url': url, 'solved_rows': solved_rows, 'rows': rows},
		errors=[] if solved_rows else ['No complete all-correct Wordle row was visible.'],
	)


def normalize_text(text: str) -> str:
	return re.sub(r'\s+', ' ', text).strip().lower()


def has_price(text: str) -> bool:
	return bool(re.search(r'([$€£]\s?\d+|\d+\s?(?:usd|eur|gbp|us\$))', text, flags=re.IGNORECASE))


async def verify_generic_visible(
	mission: Mission, session: CamoufoxSession | BrowserSession, final_result: str | None
) -> Verification:
	page = await get_current_page(session)
	url = await page_url(session, page)
	title = await page_title(session, page)
	body_text = await evaluate_page(page, "() => document.body ? document.body.innerText : ''")
	final = final_result or ''
	combined = normalize_text(f'{url} {title} {body_text[:4000]} {final}')
	history_text = normalize_text(f'{url} {title}')
	domain_ok = not mission.domains or any(domain in url for domain in mission.domains)
	visible_ok = all(normalize_text(term) in combined for term in mission.visible_terms)
	final_ok = all(normalize_text(term) in normalize_text(final) for term in mission.final_terms)
	history_ok = all(
		normalize_text(term) in combined or normalize_text(term) in history_text for term in mission.history_terms
	)
	price_ok = not mission.requires_price or has_price(f'{body_text[:4000]} {final}')
	passed = domain_ok and visible_ok and final_ok and history_ok and price_ok and len(final.strip()) >= 40
	errors = []
	if not domain_ok:
		errors.append(f'Final URL did not match expected domains: {mission.domains}')
	if not visible_ok:
		errors.append(f'Visible/final evidence missing required terms: {mission.visible_terms}')
	if not final_ok:
		errors.append(f'Final answer missing required terms: {mission.final_terms}')
	if not history_ok:
		errors.append(f'History/visible evidence missing required terms: {mission.history_terms}')
	if not price_ok:
		errors.append('Visible/final evidence did not include a price-like value.')
	if len(final.strip()) < 40:
		errors.append('Final answer was too short to verify the mission.')
	return Verification(
		passed=passed,
		details={
			'url': url,
			'title': title,
			'body_excerpt': body_text[:1000],
			'final_result': final,
			'domain_ok': domain_ok,
			'visible_ok': visible_ok,
			'final_ok': final_ok,
			'history_ok': history_ok,
			'price_ok': price_ok,
		},
		errors=errors,
	)


async def verify_mission(
	mission: Mission, session: CamoufoxSession | BrowserSession, final_result: str | None
) -> Verification:
	if mission.verifier == 'wordle_board':
		return await verify_wordle_board(session)
	if mission.verifier == 'wordle_feedback':
		return await verify_wordle_feedback(session)
	if mission.verifier == 'wordle_solved':
		return await verify_wordle_solved(session)
	return await verify_generic_visible(mission, session, final_result)


async def get_current_page(session: CamoufoxSession | BrowserSession) -> Any:
	page = await session.get_current_page()
	if page is None:
		raise RuntimeError('No current page available for verification.')
	return page


async def evaluate_page(page: Any, expression: str) -> Any:
	if isinstance(page, Page):
		return await page.evaluate(expression)
	return await page.evaluate(expression)


async def page_url(session: CamoufoxSession | BrowserSession, page: Any) -> str:
	if isinstance(page, Page):
		return page.url
	return await session.get_current_page_url()


async def page_title(session: CamoufoxSession | BrowserSession, page: Any) -> str:
	if isinstance(page, Page):
		return await page.title()
	return await session.get_current_page_title()


def build_browser_session(*, runtime: str, headless: bool, chrome_executable: Path) -> CamoufoxSession | BrowserSession:
	if runtime == 'camoufox':
		return CamoufoxSession(headless=headless)
	if not chrome_executable.exists():
		raise RuntimeError(f'Chrome executable not found: {chrome_executable}')
	return BrowserSession(
		headless=headless,
		executable_path=str(chrome_executable),
		args=CHROME_TEST_ARGS,
		enable_default_extensions=False,
		keep_alive=True,
	)


def is_sensitive_key(key: Any) -> bool:
	return isinstance(key, str) and any(part in key.lower().replace('-', '_') for part in SENSITIVE_KEY_PARTS)


def scrub(value: Any, *, key: Any = None) -> Any:
	api_key = os.environ.get('CODEX_LB_API_KEY')
	if is_sensitive_key(key):
		return '<redacted>'
	if isinstance(value, str):
		result = value
		if api_key:
			result = result.replace(api_key, '<redacted-api-key>')
		for marker in SENSITIVE_TEXT_MARKERS:
			result = redact_marker_value(result, marker)
		return result
	if isinstance(value, list):
		return [scrub(item) for item in value]
	if isinstance(value, dict):
		return {item_key: scrub(item, key=item_key) for item_key, item in value.items()}
	return value


def redact_marker_value(text: str, marker: str) -> str:
	lowered = text.lower()
	start = lowered.find(marker)
	if start < 0:
		return text
	end = start + len(marker)
	while end < len(text) and text[end] in ' :=\t':
		end += 1
	stop = end
	while stop < len(text) and not text[stop].isspace() and text[stop] not in ',;&':
		stop += 1
	return text[:end] + '<redacted>' + text[stop:]


def action_result_summary(action_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
	return [{'action': result.get('action'), 'passed': bool(result.get('passed'))} for result in action_results]


def mission_result_summary(mission_report: dict[str, Any]) -> dict[str, Any]:
	history = mission_report.get('history', {})
	verification = mission_report.get('verification', {})
	diagnostics = mission_report.get('diagnostics', {})
	final_state = diagnostics.get('final_state', {})
	return {
		'runtime': mission_report.get('runtime'),
		'mission_id': mission_report.get('mission', {}).get('id'),
		'family': mission_report.get('mission', {}).get('family'),
		'variation': mission_report.get('mission', {}).get('variation'),
		'complexity': mission_report.get('mission', {}).get('complexity'),
		'passed': bool(mission_report.get('passed')),
		'agent_success': history.get('is_successful'),
		'verifier_success': verification.get('passed'),
		'failure_class': mission_report.get('failure_class'),
		'owner_category': owner_category_for_failure_class(str(mission_report.get('failure_class') or 'unknown')),
		'duration_seconds': diagnostics.get('duration_seconds'),
		'steps': history.get('steps'),
		'action_count': diagnostics.get('actions', {}).get('count'),
		'final_url': final_state.get('url'),
		'final_title': final_state.get('title'),
		'errors': mission_report.get('errors', []),
		'verifier_errors': verification.get('errors', []),
		'runtime_tool_errors': diagnostics.get('runtime_tool_errors', []),
		'fallback_paths': diagnostics.get('fallback_paths', []),
		'candidate_rankings': diagnostics.get('candidate_rankings', []),
	}


def owner_category_for_failure_class(failure_class: str) -> str:
	if failure_class == 'model/navigation':
		return 'model'
	if failure_class == 'runtime/tooling':
		return 'runtime'
	if failure_class in {'page availability', 'challenge/interruption'}:
		return 'site'
	if failure_class == 'verifier weakness':
		return 'verifier'
	return 'unknown'


def build_benchmark_matrix_report(reports: list[dict[str, Any]]) -> dict[str, Any]:
	rows = [mission_result_summary(report) for report in reports]
	by_mission: dict[str, dict[str, Any]] = {}
	for row in rows:
		mission_id = str(row.get('mission_id'))
		by_mission.setdefault(
			mission_id,
			{
				'mission_id': mission_id,
				'family': row.get('family'),
				'variation': row.get('variation'),
				'complexity': row.get('complexity'),
				'runtimes': {},
				'delta': {},
			},
		)
		by_mission[mission_id]['runtimes'][str(row.get('runtime'))] = row

	for mission in by_mission.values():
		chrome = mission['runtimes'].get('chrome')
		camoufox = mission['runtimes'].get('camoufox')
		if chrome and camoufox:
			mission['delta'] = {
				'pass_match': chrome.get('passed') == camoufox.get('passed'),
				'failure_class_match': chrome.get('failure_class') == camoufox.get('failure_class'),
				'duration_delta_seconds': round(
					float(camoufox.get('duration_seconds') or 0) - float(chrome.get('duration_seconds') or 0),
					2,
				),
				'step_delta': (camoufox.get('steps') or 0) - (chrome.get('steps') or 0),
				'action_delta': (camoufox.get('action_count') or 0) - (chrome.get('action_count') or 0),
				'chrome_passed': chrome.get('passed'),
				'camoufox_passed': camoufox.get('passed'),
			}

	summary = {
		'total_runs': len(rows),
		'mission_count': len(by_mission),
		'passed_runs': sum(1 for row in rows if row.get('passed')),
		'failed_runs': sum(1 for row in rows if not row.get('passed')),
		'by_runtime': {},
		'by_failure_class': {
			failure_class: sum(1 for row in rows if row.get('failure_class') == failure_class)
			for failure_class in FAILURE_CLASSES
		},
		'by_owner_category': {
			owner: sum(1 for row in rows if row.get('owner_category') == owner)
			for owner in ('model', 'runtime', 'site', 'verifier', 'unknown')
		},
		'diagnostics': {
			'runtime_tool_error_runs': sum(1 for row in rows if row.get('runtime_tool_errors')),
			'fallback_path_runs': sum(1 for row in rows if row.get('fallback_paths')),
			'candidate_ranking_runs': sum(1 for row in rows if row.get('candidate_rankings')),
		},
	}
	for runtime in sorted({str(row.get('runtime')) for row in rows}):
		runtime_rows = [row for row in rows if row.get('runtime') == runtime]
		summary['by_runtime'][runtime] = {
			'runs': len(runtime_rows),
			'passed': sum(1 for row in runtime_rows if row.get('passed')),
			'failed': sum(1 for row in runtime_rows if not row.get('passed')),
		}
	report = {
		'kind': 'real_world_chrome_cdp_camoufox_benchmark_matrix',
		'summary': summary,
		'missions': list(by_mission.values()),
	}
	redacted = scrub(report)
	return {**redacted, 'json': json.dumps(redacted, indent=2, ensure_ascii=False)}


def build_parity_matrix_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
	redacted_rows = scrub(rows)
	fixtures: list[dict[str, Any]] = []
	for fixture_name in sorted({row['fixture'] for row in redacted_rows}):
		fixture_rows = [row for row in redacted_rows if row['fixture'] == fixture_name]
		baseline = next((row for row in fixture_rows if row['runtime'] == 'chrome'), fixture_rows[0])
		runtimes: dict[str, Any] = {}
		for row in fixture_rows:
			is_baseline = row is baseline
			runtimes[row['runtime']] = {
				'visible_text_parity': (
					'baseline' if is_baseline else row.get('visible_text') == baseline.get('visible_text')
				),
				'attribute_parity': 'baseline' if is_baseline else row.get('attributes') == baseline.get('attributes'),
				'actionable_count': row.get('actionable_count', 0),
				'observable_only_count': row.get('observable_only_count', 0),
				'action_result_summary': action_result_summary(row.get('action_results', [])),
			}
		fixtures.append({'fixture': fixture_name, 'runtimes': runtimes})

	report = {'kind': 'chrome_camoufox_parity_matrix', 'fixtures': fixtures}
	return {**report, 'json': json.dumps(report, indent=2, ensure_ascii=False)}


def history_summary(history) -> dict[str, Any]:
	return {
		'is_done': history.is_done(),
		'is_successful': history.is_successful(),
		'final_result': history.final_result(),
		'errors': [error for error in history.errors() if error],
		'action_names': history.action_names(),
		'urls': history.urls(),
		'steps': history.number_of_steps(),
	}


def body_excerpt(body_text: str, *, limit: int = 1000) -> str:
	return scrub(body_text[:limit])


def url_transitions(urls: list[str]) -> list[dict[str, str]]:
	return [{'from': before, 'to': after} for before, after in zip(urls, urls[1:], strict=False) if before != after]


def classify_failure(report: dict[str, Any]) -> str:
	if report.get('passed') is True:
		return 'unknown'
	text = ' '.join(
		str(item)
		for item in [
			*report.get('errors', []),
			*report.get('history', {}).get('errors', []),
			*report.get('verification', {}).get('errors', []),
			report.get('diagnostics', {}).get('final_state', {}).get('url', ''),
			report.get('diagnostics', {}).get('final_state', {}).get('title', ''),
			report.get('diagnostics', {}).get('final_state', {}).get('body_excerpt', ''),
		]
	).lower()
	if any(marker in text for marker in ('tool', 'runtime', 'detached', 'timeout', 'playwright', 'traceback')):
		return 'runtime/tooling'
	if any(marker in text for marker in ('navigate', 'navigation', 'agent did not finish', 'max steps', 'model')):
		return 'model/navigation'
	if any(marker in text for marker in ('404', '403', 'unavailable', 'dns', 'net::', 'not found')):
		return 'page availability'
	if any(marker in text for marker in ('captcha', 'challenge', 'blocked', 'interstitial', 'modal')):
		return 'challenge/interruption'
	if any(marker in text for marker in ('verifier', 'verify', 'success criteria')):
		return 'verifier weakness'
	return 'unknown'


def enrich_mission_report(
	report: dict[str, Any], *, final_state: dict[str, Any] | None, duration_seconds: float
) -> dict[str, Any]:
	history = report.get('history', {})
	action_names = history.get('action_names', [])
	runtime_tool_errors = [error for error in history.get('errors', []) if error]
	final_state = final_state or {}
	enriched = {
		**report,
		'diagnostics': {
			'final_state': {
				'url': final_state.get('url', ''),
				'title': final_state.get('title', ''),
				'body_excerpt': body_excerpt(str(final_state.get('body_text', ''))),
				'metrics': final_state.get('dom_metrics', {}),
			},
			'actions': {'names': action_names, 'count': len(action_names)},
			'duration_seconds': duration_seconds,
			'url_transitions': url_transitions(history.get('urls', [])),
			'runtime_tool_errors': runtime_tool_errors,
			'verifier': report.get('verification', {}),
		},
	}
	enriched['failure_class'] = classify_failure(enriched)
	return scrub(enriched)


async def capture_final_state(session: CamoufoxSession | BrowserSession) -> dict[str, Any]:
	page = await get_current_page(session)
	body_text = await evaluate_page(page, "() => document.body ? document.body.innerText : ''")
	dom_metrics = await evaluate_page(
		page,
		"""() => ({
			element_count: document.querySelectorAll('*').length,
			body_text_length: document.body ? document.body.innerText.length : 0
		})""",
	)
	return {
		'url': await page_url(session, page),
		'title': await page_title(session, page),
		'body_text': body_text,
		'dom_metrics': dom_metrics,
	}


async def run_mission(
	mission: Mission,
	*,
	model: str,
	base_url: str,
	headless: bool,
	runtime: str,
	chrome_executable: Path,
	pause_after_task: float,
) -> dict[str, Any]:
	start = time.monotonic()
	session = build_browser_session(runtime=runtime, headless=headless, chrome_executable=chrome_executable)
	result: dict[str, Any] = {
		'mission': asdict(mission),
		'model': model,
		'base_url': base_url,
		'runtime': runtime,
		'headless': headless,
		'started_at': datetime.now(UTC).isoformat(),
		'passed': False,
		'errors': [],
	}
	try:
		agent = Agent(
			task=f'{MISSION_PRINCIPLES}\n\nMission: {mission.task}\n\nSuccess criteria: {mission.success_criteria}',
			llm=build_llm(model=model, base_url=base_url),
			browser_session=session,
			tools=build_tools(runtime=runtime),
			use_vision=False,
			use_judge=False,
			enable_planning=False,
			initial_actions=[{'navigate': {'url': mission.url, 'new_tab': False}}],
			max_failures=3,
			max_actions_per_step=3,
			llm_timeout=180,
			step_timeout=180,
		)
		history = await asyncio.wait_for(agent.run(max_steps=mission.max_steps), timeout=mission.timeout_seconds)
		result['history'] = history_summary(history)
		verification = await verify_mission(mission, session, history.final_result())
		result['verification'] = asdict(verification)
		result['passed'] = history.is_successful() is True and verification.passed
		if history.is_successful() is not True:
			result['errors'].append(f'Agent did not finish successfully: {history.is_successful()}')
		result['errors'].extend(verification.errors)
		if pause_after_task > 0:
			await asyncio.sleep(pause_after_task)
	except Exception as exc:
		result['errors'].append(f'{type(exc).__name__}: {exc}')
		result['traceback'] = traceback.format_exc()
	finally:
		duration_seconds = round(time.monotonic() - start, 2)
		try:
			final_state = await capture_final_state(session)
		except Exception as exc:
			final_state = None
			result['errors'].append(f'Final state capture failed: {type(exc).__name__}: {exc}')
		result = enrich_mission_report(result, final_state=final_state, duration_seconds=duration_seconds)
		try:
			await session.stop()
		except Exception as exc:
			result['errors'].append(f'Browser stop failed: {type(exc).__name__}: {exc}')
	return scrub(result)


def default_report_path() -> Path:
	timestamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')
	return PROJECT_ROOT / 'artifacts' / 'real_world_kit' / timestamp / 'report.json'


async def main_async() -> int:
	args = parse_args()
	if args.list_missions:
		for mission in MISSIONS.values():
			print(f'{mission.id}\t{mission.family}\tvariation={mission.variation}\tcomplexity={mission.complexity}')
		return 0

	mission_ids = args.mission or list(DEFAULT_MISSION_IDS)
	report_path = args.report_path or default_report_path()
	report = {
		'started_at': datetime.now(UTC).isoformat(),
		'principles': [line.strip('- ') for line in MISSION_PRINCIPLES.splitlines() if line.startswith('-')],
		'missions': [],
	}
	for mission_id in mission_ids:
		mission_report = await run_mission(
			MISSIONS[mission_id],
			model=args.model,
			base_url=args.base_url,
			headless=args.headless,
			runtime=args.runtime,
			chrome_executable=args.chrome_executable,
			pause_after_task=args.pause_after_task,
		)
		report['missions'].append(mission_report)
		print(json.dumps(mission_report, indent=2, ensure_ascii=False))

	report['finished_at'] = datetime.now(UTC).isoformat()
	report['passed'] = all(mission['passed'] for mission in report['missions'])
	report['matrix'] = build_benchmark_matrix_report(report['missions'])
	report_path.parent.mkdir(parents=True, exist_ok=True)
	report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
	print(f'report_path: {report_path}')
	return 0 if report['passed'] else 1


if __name__ == '__main__':
	raise SystemExit(asyncio.run(main_async()))
