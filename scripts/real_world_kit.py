import argparse
import asyncio
import json
import os
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
SAUCE_DEMO_PASSWORD = 'secret_sauce'
DEFAULT_CHROME_EXECUTABLE = Path.home() / '.cache/ms-playwright/chromium-1217/chrome-linux64/chrome'
CHROME_TEST_ARGS = [
	'--password-store=basic',
	'--use-mock-keychain',
	'--disable-save-password-bubble',
	'--disable-features=PasswordManagerOnboarding,PasswordLeakDetection,AutofillServerCommunication',
]
SENSITIVE_KEY_PARTS = ('api_key', 'apikey', 'authorization', 'cookie', 'password', 'secret', 'token')

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


@dataclass
class Verification:
	passed: bool
	details: dict[str, Any]
	errors: list[str]


MISSIONS = {
	'wordle': Mission(
		id='wordle',
		name='Wordle daily solve',
		url='https://www.nytimes.com/games/wordle/index.html',
		task=(
			'Open Wordle and solve the daily puzzle only by playing guesses on the visible board. '
			'Close any welcome or help modal if needed. Start with a valid five-letter English word, submit it, '
			'read the visible tile feedback, and choose the next guess from that feedback. Do not visit any other '
			'website, do not inspect source code, do not use NYT JSON endpoints, and do not use any known answer list. '
			'Finish with success=True only when a row is visibly all correct/green. If you cannot solve it in six '
			'guesses, finish with success=False and summarize every guess and the blocker.'
		),
		success_criteria='A submitted Wordle row is complete and every tile in that row is correct/green.',
		max_steps=18,
		timeout_seconds=900,
	),
	'saucedemo': Mission(
		id='saucedemo',
		name='SauceDemo checkout flow',
		url='https://www.saucedemo.com/',
		task=(
			'Complete a demo checkout on SauceDemo. Log in with username standard_user and password secret_sauce. '
			'Sort products by price low to high, open the cheapest product details, add it to the cart, go to the '
			'cart, start checkout, fill first name Ada, last name Lovelace, postal code 11200, continue, and finish '
			'the order. Finish with success=True only when the page visibly says Thank you for your order.'
		),
		success_criteria='The final page visibly contains "Thank you for your order!" after completing checkout.',
		max_steps=16,
		timeout_seconds=600,
	),
	'wikipedia': Mission(
		id='wikipedia',
		name='Wikipedia research task',
		url='https://www.wikipedia.org/',
		task=(
			'Use Wikipedia to research Playwright, the software testing framework. Search Wikipedia, open the relevant '
			'article, and produce a concise final answer with the article title, a one-sentence summary, and two '
			'verifiable facts from the page. Finish with success=True only after you are on the relevant Wikipedia '
			'article and your final answer includes those three pieces of information.'
		),
		success_criteria=(
			'The browser ends on the relevant Wikipedia article and the final answer summarizes Playwright.'
		),
		max_steps=10,
		timeout_seconds=420,
	),
}


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description='Run headed real-world browser-use-camoufox missions.')
	parser.add_argument('--mission', choices=sorted(MISSIONS), action='append', help='Mission id to run; repeatable.')
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


async def verify_wordle(session: CamoufoxSession | BrowserSession) -> Verification:
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
	solved_rows = [
		''.join(tile['text'] for tile in row)
		for row in rows
		if len(row) == 5 and all(tile['text'] for tile in row) and all(tile['state'] == 'correct' for tile in row)
	]
	return Verification(
		passed=bool(solved_rows),
		details={'url': await page_url(session, page), 'solved_rows': solved_rows, 'rows': rows},
		errors=[] if solved_rows else ['No complete all-correct Wordle row was visible.'],
	)


async def verify_saucedemo(session: CamoufoxSession | BrowserSession) -> Verification:
	page = await get_current_page(session)
	body_text = await evaluate_page(page, "() => document.body ? document.body.innerText : ''")
	passed = 'Thank you for your order!' in body_text
	return Verification(
		passed=passed,
		details={'url': await page_url(session, page), 'contains_thank_you': passed, 'body_excerpt': body_text[:1000]},
		errors=[] if passed else ['Checkout completion message was not visible.'],
	)


async def verify_wikipedia(session: CamoufoxSession | BrowserSession, final_result: str | None) -> Verification:
	page = await get_current_page(session)
	title = await page_title(session, page)
	url = await page_url(session, page)
	body_text = await evaluate_page(page, "() => document.body ? document.body.innerText : ''")
	final = final_result or ''
	passed = (
		'wikipedia.org' in url
		and 'playwright' in (title + url + body_text[:2000]).lower()
		and 'playwright' in final.lower()
		and len(final.strip()) >= 80
	)
	return Verification(
		passed=passed,
		details={'url': url, 'title': title, 'final_result': final, 'body_excerpt': body_text[:1000]},
		errors=[] if passed else ['Final browser state or final answer did not verify the Playwright Wikipedia task.'],
	)


async def verify_mission(
	mission: Mission, session: CamoufoxSession | BrowserSession, final_result: str | None
) -> Verification:
	if mission.id == 'wordle':
		return await verify_wordle(session)
	if mission.id == 'saucedemo':
		return await verify_saucedemo(session)
	if mission.id == 'wikipedia':
		return await verify_wikipedia(session, final_result)
	raise ValueError(f'Unknown mission verifier: {mission.id}')


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
		result = value.replace(SAUCE_DEMO_PASSWORD, '<redacted-demo-password>')
		if api_key:
			result = result.replace(api_key, '<redacted-api-key>')
		return result
	if isinstance(value, list):
		return [scrub(item) for item in value]
	if isinstance(value, dict):
		return {item_key: scrub(item, key=item_key) for item_key, item in value.items()}
	return value


def action_result_summary(action_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
	return [{'action': result.get('action'), 'passed': bool(result.get('passed'))} for result in action_results]


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
		result['duration_seconds'] = round(time.monotonic() - start, 2)
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
	mission_ids = args.mission or ['wordle', 'saucedemo', 'wikipedia']
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
	report_path.parent.mkdir(parents=True, exist_ok=True)
	report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
	print(f'report_path: {report_path}')
	return 0 if report['passed'] else 1


if __name__ == '__main__':
	raise SystemExit(asyncio.run(main_async()))
