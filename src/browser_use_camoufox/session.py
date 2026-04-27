import json
import re
from collections.abc import Awaitable
from functools import wraps
from pathlib import Path
from typing import Any, Literal, cast

from browser_use.agent.views import ActionResult
from browser_use.browser import BrowserSession
from browser_use.browser.events import (
	BrowserStateRequestEvent,
	ClickCoordinateEvent,
	ClickElementEvent,
	CloseTabEvent,
	DialogOpenedEvent,
	FileDownloadedEvent,
	GetDropdownOptionsEvent,
	GoBackEvent,
	GoForwardEvent,
	LoadStorageStateEvent,
	NavigateToUrlEvent,
	RefreshEvent,
	SaveStorageStateEvent,
	ScrollEvent,
	ScrollToTextEvent,
	SelectDropdownOptionEvent,
	SendKeysEvent,
	StorageStateLoadedEvent,
	StorageStateSavedEvent,
	SwitchTabEvent,
	TypeTextEvent,
	UploadFileEvent,
	WaitEvent,
)
from browser_use.browser.views import BrowserStateSummary, TabInfo
from browser_use.dom.views import (
	DOMRect,
	EnhancedDOMTreeNode,
	EnhancedSnapshotNode,
	NodeType,
	SerializedDOMState,
	SimplifiedNode,
)
from browser_use.tools.service import Tools
from browser_use.tools.views import (
	FindElementsAction,
	GetDropdownOptionsAction,
	SaveAsPdfAction,
	ScreenshotAction,
	ScrollAction,
	SearchPageAction,
	SelectDropdownOptionAction,
	UploadFileAction,
)
from camoufox.async_api import AsyncCamoufox
from playwright.async_api import Browser, BrowserContext, Error, FloatRect, Page
from pydantic import BaseModel

from browser_use_camoufox.compat.detector import check_browser_use_compatibility

_MCP_COMPAT_APPLIED = False
DEFAULT_FIND_ELEMENT_ATTRIBUTES = [
	'id',
	'class',
	'name',
	'type',
	'role',
	'href',
	'title',
	'value',
	'placeholder',
	'alt',
	'aria-label',
	'aria-expanded',
	'aria-checked',
	'aria-selected',
	'aria-disabled',
	'data-testid',
	'data-test',
	'data-value',
	'data-state',
]
OBSERVABLE_ELEMENT_ATTRIBUTE = 'data-browser-use-camoufox-observable'
SEMANTIC_EVIDENCE_ATTRIBUTE = 'data-browser-use-camoufox-semantic-evidence'
REDACTED_ATTRIBUTE_VALUE = '[redacted]'
MAX_SAFE_ATTRIBUTE_VALUE_LENGTH = 120
MAX_SEMANTIC_EVIDENCE_LENGTH = 240
SENSITIVE_ATTRIBUTE_MARKERS = (
	'api-key',
	'apikey',
	'auth',
	'cookie',
	'csrf',
	'jwt',
	'key',
	'nonce',
	'password',
	'secret',
	'session',
	'token',
)
CLICK_TIMEOUT_MS = 5_000
PLAYWRIGHT_SPECIAL_KEYS = frozenset(
	{
		'Alt',
		'ArrowDown',
		'ArrowLeft',
		'ArrowRight',
		'ArrowUp',
		'Backspace',
		'Control',
		'Delete',
		'End',
		'Enter',
		'Escape',
		'F1',
		'F2',
		'F3',
		'F4',
		'F5',
		'F6',
		'F7',
		'F8',
		'F9',
		'F10',
		'F11',
		'F12',
		'Home',
		'Insert',
		'Meta',
		'PageDown',
		'PageUp',
		'Shift',
		'Space',
		'Tab',
	}
)


class NoFakeCDPClient:
	def __bool__(self) -> bool:
		return False

	def __getattr__(self, name: str) -> Any:
		raise RuntimeError(_no_fake_cdp_message('Raw CDP access'))

	async def __aenter__(self) -> 'NoFakeCDPClient':
		raise RuntimeError(_no_fake_cdp_message('Raw CDP access'))

	async def __aexit__(self, *args: Any) -> None:
		return None


def _no_fake_cdp_message(capability: str) -> str:
	return (
		f'{capability} is unavailable for CamoufoxSession; use registered Camoufox tool '
		'overrides or Playwright-backed browser-use APIs. no fake CDP behavior is provided.'
	)


UNSUPPORTED_PROFILE_MAPPINGS = frozenset({'traces_dir', 'proxy', 'disable_security', 'deterministic_rendering'})


def apply_camoufox_mcp_compat() -> None:
	global _MCP_COMPAT_APPLIED
	if _MCP_COMPAT_APPLIED:
		return

	from browser_use.mcp.server import BrowserUseServer

	original_get_html = BrowserUseServer._get_html
	original_list_sessions = BrowserUseServer._list_sessions

	@wraps(original_get_html)
	async def _get_html(self, selector: str | None = None):
		if isinstance(self.browser_session, CamoufoxSession):
			self._update_session_activity(self.browser_session.id)
			return await self.browser_session.get_html(selector)
		return await original_get_html(self, selector)

	@wraps(original_list_sessions)
	async def _list_sessions(self):
		if not self.active_sessions:
			return 'No active browser sessions'
		if not any(isinstance(data['session'], CamoufoxSession) for data in self.active_sessions.values()):
			return await original_list_sessions(self)

		import time

		sessions_info = []
		for session_id, session_data in self.active_sessions.items():
			session = session_data['session']
			created_at = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(session_data['created_at']))
			last_activity = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(session_data['last_activity']))
			if isinstance(session, CamoufoxSession):
				is_active = await session.is_active()
				current_url = await session.get_current_page_url()
			else:
				is_active = getattr(session, 'cdp_client', None) is not None
				current_url = session_data.get('url', 'Unknown')
			sessions_info.append(
				{
					'session_id': session_id,
					'created_at': created_at,
					'last_activity': last_activity,
					'active': is_active,
					'current_url': current_url,
					'age_minutes': (time.time() - session_data['created_at']) / 60,
				}
			)
		return json.dumps(sessions_info, indent=2)

	BrowserUseServer._get_html = _get_html
	BrowserUseServer._list_sessions = _list_sessions
	_MCP_COMPAT_APPLIED = True


def register_camoufox_tools(tools: Tools) -> None:
	@tools.registry.action(
		'Search page text for a pattern without CDP when using Camoufox.',
		param_model=SearchPageAction,
	)
	async def search_page(params: SearchPageAction, browser_session: BrowserSession):
		if not isinstance(browser_session, CamoufoxSession):
			raise RuntimeError('Camoufox search_page override requires CamoufoxSession.')
		return await browser_session.search_page(params)

	@tools.registry.action(
		'Query DOM elements by CSS selector without CDP when using Camoufox.',
		param_model=FindElementsAction,
	)
	async def find_elements(params: FindElementsAction, browser_session: BrowserSession):
		if not isinstance(browser_session, CamoufoxSession):
			raise RuntimeError('Camoufox find_elements override requires CamoufoxSession.')
		return await browser_session.find_elements(params)

	@tools.registry.action(
		'Execute browser JavaScript without CDP when using Camoufox.',
		terminates_sequence=True,
	)
	async def evaluate(code: str, browser_session: BrowserSession):
		if not isinstance(browser_session, CamoufoxSession):
			raise RuntimeError('Camoufox evaluate override requires CamoufoxSession.')
		return await browser_session.evaluate_script(code)

	@tools.registry.action(
		'Scroll by pages without CDP when using Camoufox.',
		param_model=ScrollAction,
	)
	async def scroll(params: ScrollAction, browser_session: BrowserSession):
		if not isinstance(browser_session, CamoufoxSession):
			raise RuntimeError('Camoufox scroll override requires CamoufoxSession.')
		return await browser_session.scroll_action(params)

	@tools.registry.action(
		'Take a screenshot of the current viewport.',
		param_model=ScreenshotAction,
	)
	async def screenshot(params: ScreenshotAction, browser_session: BrowserSession, file_system):
		if not isinstance(browser_session, CamoufoxSession):
			raise RuntimeError('Camoufox screenshot override requires CamoufoxSession.')
		return await browser_session.screenshot_action(params, file_system)

	@tools.registry.action(
		'Save the current page as a PDF file.',
		param_model=SaveAsPdfAction,
	)
	async def save_as_pdf(params: SaveAsPdfAction, browser_session: BrowserSession, file_system):
		if not isinstance(browser_session, CamoufoxSession):
			raise RuntimeError('Camoufox save_as_pdf override requires CamoufoxSession.')
		return await browser_session.save_as_pdf_action(params, file_system)

	@tools.registry.action('', param_model=GetDropdownOptionsAction)
	async def dropdown_options(params: GetDropdownOptionsAction, browser_session: BrowserSession):
		if not isinstance(browser_session, CamoufoxSession):
			raise RuntimeError('Camoufox dropdown_options override requires CamoufoxSession.')
		return await browser_session.dropdown_options_action(params)

	@tools.registry.action('Set the option of a <select> element.', param_model=SelectDropdownOptionAction)
	async def select_dropdown(params: SelectDropdownOptionAction, browser_session: BrowserSession):
		if not isinstance(browser_session, CamoufoxSession):
			raise RuntimeError('Camoufox select_dropdown override requires CamoufoxSession.')
		return await browser_session.select_dropdown_action(params)

	@tools.registry.action('', param_model=UploadFileAction)
	async def upload_file(
		params: UploadFileAction, browser_session: BrowserSession, available_file_paths: list[str], file_system
	):
		if not isinstance(browser_session, CamoufoxSession):
			raise RuntimeError('Camoufox upload_file override requires CamoufoxSession.')
		return await browser_session.upload_file_action(params, available_file_paths, file_system)


class CamoufoxSession(BrowserSession):
	def __init__(self, *, headless: bool | None = None, **launch_options: Any) -> None:
		self._reject_unsupported_profile_mappings(launch_options)
		super().__init__(headless=headless)
		context_option_names = {
			'accept_downloads',
			'downloads_path',
			'geolocation',
			'headers',
			'init_scripts',
			'permissions',
			'record_har_content',
			'record_har_mode',
			'record_har_path',
			'record_video_dir',
			'record_video_size',
			'storage_state',
		}
		raw_options = {'headless': headless, **launch_options}
		self._context_options = {
			key: value for key, value in raw_options.items() if key in context_option_names and value is not None
		}
		self._launch_options = {
			key: value for key, value in raw_options.items() if key not in context_option_names and value is not None
		}
		self._camoufox: AsyncCamoufox | None = None
		self._browser: Browser | BrowserContext | None = None
		self._context: BrowserContext | None = None
		self._page: Page | None = None
		self._navigation_history: list[str] = []
		self._navigation_history_index = -1
		self._cached_selector_map: dict[int, EnhancedDOMTreeNode] = {}
		self._selector_targets: dict[int, dict[str, Any]] = {}
		self._recording_rejected = False
		object.__setattr__(self, '_last_click_diagnostics', None)
		object.__setattr__(self, '_last_keyboard_diagnostics', None)
		self._register_camoufox_event_handlers()

	async def start(self) -> None:
		compatibility = check_browser_use_compatibility()
		if not compatibility.ok:
			raise RuntimeError(f'Unsupported browser-use runtime: {", ".join(compatibility.errors)}')
		if self._browser is not None:
			return

		self._camoufox = AsyncCamoufox(**self._launch_options)
		self._browser = await self._camoufox.__aenter__()
		self._context = await self._ensure_context(self._browser)
		self._page = await self._context.new_page()

	async def stop(self) -> None:
		if self._context is not None:
			await self._context.close()
		if self._camoufox is not None:
			await self._camoufox.__aexit__(None, None, None)
		await self.event_bus.stop(clear=True, timeout=5)
		self._register_camoufox_event_handlers()
		self._camoufox = None
		self._browser = None
		self._context = None
		self._page = None
		self._navigation_history = []
		self._navigation_history_index = -1

	async def navigate_to(
		self,
		url: str,
		new_tab: bool = False,
		wait_until: Literal['load', 'domcontentloaded', 'networkidle', 'commit'] = 'load',
		timeout_ms: int | None = None,
	) -> None:
		page = await self._ensure_page(new_tab=new_tab)
		await page.goto(url, wait_until=wait_until, timeout=timeout_ms)
		if new_tab:
			self._navigation_history = []
			self._navigation_history_index = -1
		self._record_navigation_url(page.url)

	async def on_NavigateToUrlEvent(self, event: NavigateToUrlEvent) -> None:
		await self.navigate_to(
			event.url,
			new_tab=event.new_tab,
			wait_until=event.wait_until,
			timeout_ms=event.timeout_ms,
		)

	async def on_GoBackEvent(self, event: GoBackEvent) -> None:
		page = await self._ensure_page()
		response = await page.go_back(wait_until='load')
		if response is None and self._navigation_history_index > 0:
			self._navigation_history_index -= 1
			await page.goto(self._navigation_history[self._navigation_history_index], wait_until='load')

	async def on_GoForwardEvent(self, event: GoForwardEvent) -> None:
		page = await self._ensure_page()
		response = await page.go_forward(wait_until='load')
		if response is None and self._navigation_history_index < len(self._navigation_history) - 1:
			self._navigation_history_index += 1
			await page.goto(self._navigation_history[self._navigation_history_index], wait_until='load')

	async def on_RefreshEvent(self, event: RefreshEvent) -> None:
		page = await self._ensure_page()
		await page.goto(page.url, wait_until='domcontentloaded')

	async def on_WaitEvent(self, event: WaitEvent) -> None:
		page = await self._ensure_page()
		await page.wait_for_timeout(min(event.seconds, event.max_seconds) * 1000)

	async def on_SwitchTabEvent(self, event: SwitchTabEvent) -> str | None:
		if self._context is None:
			return None
		if event.target_id is None:
			self._page = self._context.pages[-1] if self._context.pages else None
			return self._tab_target_id(len(self._context.pages) - 1) if self._page is not None else None
		for index, page in enumerate(self._context.pages):
			if self._tab_target_matches(index, event.target_id):
				self._page = page
				await page.bring_to_front()
				return self._tab_target_id(index)
		return None

	async def on_CloseTabEvent(self, event: CloseTabEvent) -> None:
		if self._context is None:
			return
		pages = list(self._context.pages)
		for index, page in enumerate(pages):
			if self._tab_target_matches(index, event.target_id):
				was_current = page == self._page
				await page.close()
				remaining_pages = self._context.pages
				if was_current:
					self._page = remaining_pages[min(index, len(remaining_pages) - 1)] if remaining_pages else None
				return

	async def on_BrowserStateRequestEvent(self, event: BrowserStateRequestEvent) -> BrowserStateSummary:
		page = await self._ensure_page()
		screenshot = None
		if event.include_screenshot:
			import base64

			screenshot = base64.b64encode(await self.take_screenshot()).decode('utf-8')
		return BrowserStateSummary(
			dom_state=await self._get_dom_state()
			if event.include_dom
			else SerializedDOMState(_root=None, selector_map={}),
			url=page.url,
			title=await page.title(),
			tabs=await self.get_tabs(),
			screenshot=screenshot,
		)

	async def on_ClickElementEvent(self, event: ClickElementEvent) -> dict[str, Any] | None:
		if event.node.attributes.get('type') == 'file':
			raise RuntimeError('File inputs require upload support; use the upload-file compatibility path instead.')
		if event.node.attributes.get('data-browser-use-camoufox-disabled') == 'true':
			raise RuntimeError(f'Element {event.node.node_id} is disabled and cannot be clicked.')
		if event.node.attributes.get(OBSERVABLE_ELEMENT_ATTRIBUTE) == 'true':
			raise RuntimeError(
				f'Element {event.node.node_id} is observable but not clickable. '
				'Use the keyboard, an interactive control, or evaluate/read tools instead.'
			)
		node = await self._relocalize_action_node(event.node)
		before = await self._capture_click_state(node)
		try:
			await self._locator_for_node(node).click(button=event.button, timeout=CLICK_TIMEOUT_MS)
		except Error as exc:
			raise RuntimeError(self._click_error_message(node, exc)) from exc
		after = await self._capture_click_state(node)
		object.__setattr__(self, '_last_click_diagnostics', self._click_change_diagnostics(before, after))
		return None

	async def on_ClickCoordinateEvent(self, event: ClickCoordinateEvent) -> dict[str, int]:
		page = await self._ensure_page()
		await page.mouse.click(event.coordinate_x, event.coordinate_y, button=event.button)
		return {'click_x': event.coordinate_x, 'click_y': event.coordinate_y}

	async def on_TypeTextEvent(self, event: TypeTextEvent) -> dict[str, Any] | None:
		if event.node.attributes.get('type') == 'file':
			raise RuntimeError('File inputs require upload support; use the upload-file compatibility path instead.')
		if event.node.attributes.get('data-browser-use-camoufox-disabled') == 'true':
			raise RuntimeError(f'Element {event.node.node_id} is disabled and cannot be edited.')
		if event.node.attributes.get(OBSERVABLE_ELEMENT_ATTRIBUTE) == 'true':
			raise RuntimeError(
				f'Element {event.node.node_id} is observable but not editable. '
				'Use an input, textarea, contenteditable element, or keyboard send_keys instead.'
			)
		locator = self._locator_for_node(event.node)
		if event.clear:
			await locator.fill('')
		await locator.fill(event.text)
		return None

	async def on_ScrollEvent(self, event: ScrollEvent) -> None:
		page = await self._ensure_page()
		if event.node is not None:
			x_delta = event.amount if event.direction == 'right' else -event.amount if event.direction == 'left' else 0
			y_delta = event.amount if event.direction == 'down' else -event.amount if event.direction == 'up' else 0
			await self._scroll_nearest_container(event.node, x_delta, y_delta)
			return
		x_delta = event.amount if event.direction == 'right' else -event.amount if event.direction == 'left' else 0
		y_delta = event.amount if event.direction == 'down' else -event.amount if event.direction == 'up' else 0
		await page.evaluate('(delta) => window.scrollBy(delta.x, delta.y)', {'x': x_delta, 'y': y_delta})

	async def on_ScrollToTextEvent(self, event: ScrollToTextEvent) -> None:
		page = await self._ensure_page()
		locator = page.get_by_text(event.text, exact=False).first
		if await locator.count() == 0:
			raise RuntimeError(f'Text not found for Camoufox scroll-to-text: {event.text}')
		await locator.scroll_into_view_if_needed()

	async def on_SendKeysEvent(self, event: SendKeysEvent) -> None:
		page = await self._ensure_page()
		kind = self._classify_keyboard_input(event.keys)
		before = await self._active_element_diagnostics(page)
		if kind == 'press':
			await self._prepare_keyboard_focus(page)
		after_focus = await self._active_element_diagnostics(page)
		if kind == 'text':
			await page.keyboard.type(event.keys)
		elif kind == 'invalid':
			raise RuntimeError(
				f'Ambiguous keyboard input for Camoufox send_keys: {event.keys!r}. '
				'Use printable text, a Playwright special key, or a complete key chord like "Control+A".'
			)
		else:
			await page.keyboard.press(event.keys)
		after = await self._active_element_diagnostics(page)
		object.__setattr__(
			self,
			'_last_keyboard_diagnostics',
			{'before': before, 'after_focus': after_focus, 'after': after},
		)

	async def on_GetDropdownOptionsEvent(self, event: GetDropdownOptionsEvent) -> dict[str, str]:
		return await self.get_dropdown_options(event.node)

	async def on_SelectDropdownOptionEvent(self, event: SelectDropdownOptionEvent) -> dict[str, str]:
		return await self.select_dropdown_option(event.node, event.text)

	async def on_UploadFileEvent(self, event: UploadFileEvent) -> None:
		await self.upload_file(event.node, event.file_path)

	async def on_SaveStorageStateEvent(self, event: SaveStorageStateEvent) -> StorageStateSavedEvent:
		context = await self._ensure_context_started()
		path = event.path or str(Path('storage_state.json').resolve())
		state = await context.storage_state(path=path)
		return StorageStateSavedEvent(
			path=path,
			cookies_count=len(state.get('cookies', [])),
			origins_count=len(state.get('origins', [])),
		)

	async def on_LoadStorageStateEvent(self, event: LoadStorageStateEvent) -> StorageStateLoadedEvent:
		if not event.path:
			raise RuntimeError('Loading storage state requires an explicit path for CamoufoxSession.')
		if self._browser is not None:
			await self.stop()
		self._context_options['storage_state'] = event.path
		await self.start()
		context = await self._ensure_context_started()
		state = await context.storage_state()
		return StorageStateLoadedEvent(
			path=event.path,
			cookies_count=len(state.get('cookies', [])),
			origins_count=len(state.get('origins', [])),
		)

	async def get_current_page_url(self) -> str:
		return self._page.url if self._page is not None else 'about:blank'

	async def get_current_page_title(self) -> str:
		if self._page is None:
			return 'Unknown page title'
		return await self._page.title()

	async def take_screenshot(
		self,
		path: str | None = None,
		full_page: bool = False,
		format: Literal['png', 'jpeg'] = 'png',
		quality: int | None = None,
		clip: FloatRect | None = None,
	) -> bytes:
		page = await self._ensure_page()
		screenshot = await page.screenshot(path=path, full_page=full_page, type=format, quality=quality, clip=clip)
		if path:
			Path(path).write_bytes(screenshot)
		return screenshot

	async def search_page(self, params: SearchPageAction) -> ActionResult:
		page = await self._ensure_page()
		data = await page.evaluate(
			"""(args) => {
				const scope = args.cssScope ? document.querySelector(args.cssScope) : document.body;
				if (!scope) return {error: `CSS scope selector not found: ${args.cssScope}`, matches: [], total: 0};
				const normalizeVisibleText = (value) => (value || '').replace(/\\s+/g, ' ').trim();
				const isSensitive = (name) => {
					const normalized = String(name || '').toLowerCase();
					return args.sensitiveMarkers.some((marker) => normalized.includes(marker));
				};
				const safeAttributesFor = (element) => {
					const attributes = {};
					for (const name of args.attributes || []) {
						if (isSensitive(name)) continue;
						const value = element.getAttribute(name);
						if (value !== null) {
							attributes[name] = normalizeVisibleText(value).slice(0, args.maxAttributeLength);
						}
					}
					return attributes;
				};
				let fullText = '';
				const nodeOffsets = [];
				const collectSegments = (element) => {
					if (!element) return;
					const style = window.getComputedStyle(element);
					if (style.visibility === 'hidden' || style.display === 'none') return;
					const childElements = Array.from(element.children).filter((child) => {
						const childStyle = window.getComputedStyle(child);
						return childStyle.visibility !== 'hidden' && childStyle.display !== 'none';
					});
					if (childElements.length) {
						for (const child of childElements) collectSegments(child);
						return;
					}
					const text = normalizeVisibleText(element.innerText);
					if (!text) return;
					const prefix = fullText ? ' ' : '';
					const offset = fullText.length + prefix.length;
					fullText += `${prefix}${text}`;
					nodeOffsets.push({
						offset,
						length: text.length,
						path: pathFor(element),
						attributes: safeAttributesFor(element),
					});
				};
				collectSegments(scope);
				return {
					fullText,
					nodeOffsets,
				};
				function pathFor(element) {
					const parts = [];
					let current = element;
					while (current && current !== document.body && current !== document) {
						let desc = current.tagName ? current.tagName.toLowerCase() : '';
						if (!desc) break;
						if (current.id) desc += `#${current.id}`;
						else if (typeof current.className === 'string' && current.className.trim()) {
							desc += `.${current.className.trim().split(/\\s+/).slice(0, 2).join('.')}`;
						}
						parts.unshift(desc);
						current = current.parentElement;
					}
					return parts.join(' > ');
				}
			}""",
			{
				'attributes': DEFAULT_FIND_ELEMENT_ATTRIBUTES,
				'cssScope': params.css_scope,
				'maxAttributeLength': MAX_SAFE_ATTRIBUTE_VALUE_LENGTH,
				'sensitiveMarkers': list(SENSITIVE_ATTRIBUTE_MARKERS),
			},
		)
		if data.get('error'):
			return ActionResult(error=f'search_page: {data["error"]}')
		body_text = data['fullText']
		flags = 0 if params.case_sensitive else re.IGNORECASE
		try:
			pattern = re.compile(params.pattern if params.regex else re.escape(params.pattern), flags)
		except re.error as exc:
			return ActionResult(error=f'search_page: Invalid regex pattern: {exc}')
		all_matches = list(pattern.finditer(body_text))
		if not all_matches:
			return ActionResult(
				extracted_content=f'No matches found for "{params.pattern}" on page.',
				long_term_memory='No matches found.',
			)
		match_count = len(all_matches)
		plural = 'es' if match_count != 1 else ''
		lines = [f'Found {match_count} match{plural} for "{params.pattern}" on page:', '']
		for result_index, match in enumerate(all_matches[: params.max_results], start=1):
			start = max(0, match.start() - params.context_chars)
			end = min(len(body_text), match.end() + params.context_chars)
			context = f'{"..." if start > 0 else ""}{body_text[start:end]}{"..." if end < len(body_text) else ""}'
			element = self._element_evidence_for_match(data['nodeOffsets'], match.start())
			location_parts = []
			if element.get('path'):
				location_parts.append(f'in {element["path"]}')
			if element.get('attributes'):
				attrs = ' '.join(
					f'{key}="{value}"' for key, value in cast(dict[str, str], element['attributes']).items()
				)
				if attrs:
					location_parts.append(attrs)
			location = f' ({"; ".join(location_parts)})' if location_parts else ''
			lines.append(f'[{result_index}] {context}{location}')
		if len(all_matches) > params.max_results:
			lines.append(
				f'\n... showing {params.max_results} of {match_count} total matches. Increase max_results to see more.'
			)
		content = '\n'.join(lines)
		return ActionResult(
			extracted_content=content,
			long_term_memory=f'Searched page for "{params.pattern}": {len(all_matches)} match(es) found.',
		)

	async def find_elements(self, params: FindElementsAction) -> ActionResult:
		page = await self._ensure_page()
		attributes = params.attributes if params.attributes is not None else DEFAULT_FIND_ELEMENT_ATTRIBUTES
		data = await page.locator(params.selector).evaluate_all(
			"""(elements, args) => elements.slice(0, args.maxResults).map((element) => {
				const sensitiveMarkers = args.sensitiveMarkers || [];
				const normalizeText = (value) => (value || '').replace(/\\s+/g, ' ').trim();
				const isSensitive = (name) => {
					const normalized = String(name || '').toLowerCase();
					return sensitiveMarkers.some((marker) => normalized.includes(marker));
				};
				const attributes = {};
				for (const name of args.attributes || []) {
					if (isSensitive(name)) continue;
					const value = element.getAttribute(name);
					if (value !== null) attributes[name] = normalizeText(value).slice(0, args.maxAttributeLength);
				}
				const rawText = args.includeText
					? (element.innerText || element.value || element.getAttribute('aria-label') || '')
					: '';
				return {
					tag: element.tagName.toLowerCase(),
					text: normalizeText(rawText),
					attributes,
					path: pathFor(element),
				};
				function pathFor(element) {
					const parts = [];
					let current = element;
					while (current && current !== document.body && current !== document) {
						let desc = current.tagName ? current.tagName.toLowerCase() : '';
						if (!desc) break;
						if (current.id) desc += `#${current.id}`;
						else if (typeof current.className === 'string' && current.className.trim()) {
							desc += `.${current.className.trim().split(/\\s+/).slice(0, 2).join('.')}`;
						}
						parts.unshift(desc);
						current = current.parentElement;
					}
					return parts.join(' > ');
				}
			})""",
			{
				'attributes': attributes,
				'includeText': params.include_text,
				'maxAttributeLength': MAX_SAFE_ATTRIBUTE_VALUE_LENGTH,
				'maxResults': params.max_results,
				'sensitiveMarkers': list(SENSITIVE_ATTRIBUTE_MARKERS),
			},
		)
		lines = [f'Found {len(data)} elements matching "{params.selector}":']
		for item in data:
			attrs = ' '.join(f'{key}="{value}"' for key, value in item['attributes'].items() if value is not None)
			text = f' {item["text"]}' if item['text'] else ''
			path = f' path: {item["path"]}' if item.get('path') else ''
			lines.append(f'- <{item["tag"]} {attrs}>{text}{path}'.rstrip())
		return ActionResult(extracted_content='\n'.join(lines), long_term_memory=lines[0])

	async def evaluate_script(self, code: str) -> ActionResult:
		page = await self._ensure_page()
		value = await page.evaluate(code)
		result = self._stringify_js_result(value)
		return ActionResult(extracted_content=result, long_term_memory=result)

	async def screenshot_action(self, params: ScreenshotAction, file_system) -> ActionResult:
		if not params.file_name:
			return ActionResult(
				extracted_content='Requested screenshot for next observation',
				metadata={'include_screenshot': True},
			)
		file_name = params.file_name if params.file_name.lower().endswith('.png') else f'{params.file_name}.png'
		if file_system is None:
			return ActionResult(error='Screenshot file output requires a Browser-Use file system.')
		file_name = file_system.sanitize_filename(file_name)
		file_path = file_system.get_dir() / file_name
		file_path.write_bytes(await self.take_screenshot(full_page=False))
		return ActionResult(
			extracted_content=f'Screenshot saved to {file_name}',
			long_term_memory=f'Screenshot saved to {file_name}. Full path: {file_path}',
			attachments=[str(file_path)],
		)

	async def dropdown_options_action(self, params: GetDropdownOptionsAction) -> ActionResult:
		node = await self._get_fresh_node(params.index)
		if node is None:
			return self._missing_index_result(params.index)
		data = await self.get_dropdown_options(node)
		if data.get('error'):
			return ActionResult(error=data['error'])
		return ActionResult(
			extracted_content=data['short_term_memory'],
			long_term_memory=data['long_term_memory'],
			include_extracted_content_only_once=True,
		)

	async def select_dropdown_action(self, params: SelectDropdownOptionAction) -> ActionResult:
		node = await self._get_fresh_node(params.index)
		if node is None:
			return self._missing_index_result(params.index)
		data = await self.select_dropdown_option(node, params.text)
		if data.get('success') == 'true':
			return ActionResult(
				extracted_content=data['message'],
				long_term_memory=f"Selected dropdown option '{params.text}' at index {params.index}",
			)
		return ActionResult(error=data.get('error', f'Failed to select option: {params.text}'))

	async def upload_file_action(
		self, params: UploadFileAction, available_file_paths: list[str], file_system
	) -> ActionResult:
		path = Path(params.path)
		if params.path not in (available_file_paths or []):
			file_obj = file_system.get_file(params.path) if file_system is not None else None
			if file_obj is None:
				return ActionResult(error=f'File path {params.path} is not available.')
			if file_system is None:
				return ActionResult(error='File upload path resolution requires a Browser-Use file system.')
			path = file_system.get_dir() / params.path
		if not path.exists():
			return ActionResult(error=f'File {path} does not exist')
		node = await self._get_fresh_node(params.index)
		if node is None:
			return self._missing_index_result(params.index)
		await self.upload_file(node, str(path))
		return ActionResult(
			extracted_content=f'Uploaded file {path.name}', long_term_memory=f'Uploaded file {path.name}'
		)

	async def scroll_action(self, params: ScrollAction) -> ActionResult:
		page = await self._ensure_page()
		node = await self._get_fresh_node(params.index) if params.index not in (None, 0) else None
		if params.index not in (None, 0) and node is None:
			return self._missing_index_result(params.index)
		viewport_height = await page.evaluate('window.innerHeight || document.documentElement.clientHeight || 1000')
		pixels = int(float(viewport_height or 1000) * params.pages)
		direction = 'down' if params.down else 'up'
		x_delta = 0
		y_delta = abs(pixels) if params.down else -abs(pixels)
		diagnostics = (
			await self._scroll_nearest_container(node, x_delta, y_delta)
			if node is not None
			else await self._scroll_page_with_diagnostics(x_delta, y_delta)
		)
		target = f' element {params.index}' if params.index not in (None, 0) else ''
		memory = f'Scrolled {direction}{target} {abs(pixels)}px'
		if diagnostics['blocker'] != 'moved':
			memory = f'{memory} (no-op: {diagnostics["blocker"]})'
		return ActionResult(
			extracted_content=memory, long_term_memory=memory, metadata={'scroll_diagnostics': diagnostics}
		)

	async def save_as_pdf_action(self, params: SaveAsPdfAction, file_system) -> ActionResult:
		page = await self._ensure_page()
		file_name = params.file_name or await self.get_current_page_title()
		file_name = file_name if file_name.lower().endswith('.pdf') else f'{file_name}.pdf'
		file_name = file_system.sanitize_filename(file_name)
		file_path = file_system.get_dir() / file_name
		try:
			await page.pdf(
				path=str(file_path),
				print_background=params.print_background,
				landscape=params.landscape,
				scale=params.scale,
			)
		except Error as exc:
			return ActionResult(error=f'PDF generation is unsupported by this Camoufox runtime: {exc}')
		return ActionResult(
			extracted_content=f'Saved page as PDF: {file_name} ({file_path.stat().st_size:,} bytes)',
			long_term_memory=f'Saved page as PDF: {file_name}. Full path: {file_path}',
			attachments=[str(file_path)],
		)

	async def get_current_page(self) -> Page:
		return await self._ensure_page()

	async def get_html(self, selector: str | None = None) -> str:
		page = await self._ensure_page()
		if selector:
			html = await page.locator(selector).first.evaluate('element => element.outerHTML')
			return html or f'No element found for selector: {selector}'
		return await page.content()

	async def is_active(self) -> bool:
		return self._context is not None and self._page is not None and not self._page.is_closed()

	async def wait_for_dialog(
		self,
		accept: bool = True,
		prompt_text: str | None = None,
		trigger: Awaitable[Any] | None = None,
	) -> DialogOpenedEvent:
		page = await self._ensure_page()

		async def handle_dialog(dialog):
			if accept:
				await dialog.accept(prompt_text)
			else:
				await dialog.dismiss()

		page.once('dialog', handle_dialog)
		async with page.expect_event('dialog') as event_info:
			if trigger is None:
				raise RuntimeError('Dialog handling requires a real page action that triggers a dialog.')
			await trigger
		dialog = await event_info.value
		return DialogOpenedEvent(dialog_type=dialog.type, message=dialog.message, url=page.url, frame_id=None)

	async def download_from(self, selector: str) -> FileDownloadedEvent:
		page = await self._ensure_page()
		async with page.expect_download() as download_info:
			await page.locator(selector).click()
		download = await download_info.value
		target = self._download_target(download.suggested_filename)
		await download.save_as(target)
		return FileDownloadedEvent(
			guid=None,
			url=download.url,
			path=str(target),
			file_name=download.suggested_filename,
			file_size=target.stat().st_size,
		)

	def unsupported_capabilities(self) -> dict[str, str]:
		return {
			'captcha': 'unsupported_capability',
			'closed_shadow_roots': 'not_introspectable',
			'coverage': 'not_applicable_no_cdp',
			'profiling': 'not_applicable_no_cdp',
			'tracing': 'not_applicable_no_cdp',
			**{option: 'unsupported_profile_mapping' for option in sorted(UNSUPPORTED_PROFILE_MAPPINGS)},
		}

	def extra_http_headers(self) -> dict[str, str]:
		return dict(self._context_options.get('headers') or {})

	@property
	def last_click_diagnostics(self) -> dict[str, Any] | None:
		diagnostics = getattr(self, '_last_click_diagnostics', None)
		return dict(diagnostics) if isinstance(diagnostics, dict) else None

	@property
	def last_keyboard_diagnostics(self) -> dict[str, Any] | None:
		diagnostics = getattr(self, '_last_keyboard_diagnostics', None)
		return dict(diagnostics) if isinstance(diagnostics, dict) else None

	async def get_selector_map(self) -> dict[int, EnhancedDOMTreeNode]:
		return (await self._get_dom_state()).selector_map

	async def get_dropdown_options(self, node: EnhancedDOMTreeNode) -> dict[str, str]:
		data = await self._locator_for_node(node).evaluate(
			"""element => {
				const role = element.getAttribute('role');
				let candidates = [];
				if (element.tagName.toLowerCase() === 'select') {
					candidates = Array.from(element.querySelectorAll('option'));
				} else if (role === 'listbox') {
					candidates = Array.from(element.querySelectorAll('[role="option"]'));
				} else if (role === 'menu') {
					candidates = Array.from(element.querySelectorAll('[role="menuitem"], [role="option"]'));
				} else {
					return {error: `Element is not a dropdown: <${element.tagName.toLowerCase()}>`};
				}
				return {options: candidates.map((option, index) => ({
					index,
					text: (option.textContent || '').trim(),
					value: option.value || option.getAttribute('data-value') || option.getAttribute('value') || '',
					selected: option.selected === true || option.getAttribute('aria-selected') === 'true',
				}))};
			}"""
		)
		if data.get('error'):
			return {'error': str(data['error']), 'short_term_memory': '', 'long_term_memory': ''}
		options = data.get('options') or []
		if not options:
			return {
				'short_term_memory': 'No dropdown options found.',
				'long_term_memory': 'No dropdown options found.',
			}
		lines = [f'{option["index"]}: {option["text"]}' for option in options]
		content = 'Dropdown options:\n' + '\n'.join(lines)
		return {'short_term_memory': content, 'long_term_memory': content}

	async def select_dropdown_option(self, node: EnhancedDOMTreeNode, text: str) -> dict[str, str]:
		locator = self._locator_for_node(node)
		data = await locator.evaluate(
			"""(element, text) => {
				const role = element.getAttribute('role');
				if (element.tagName.toLowerCase() === 'select') return {native: true};
				let candidates = [];
				if (role === 'listbox') {
					candidates = Array.from(element.querySelectorAll('[role="option"]'));
				} else if (role === 'menu') {
					candidates = Array.from(element.querySelectorAll('[role="menuitem"], [role="option"]'));
				} else {
					return {error: `Element is not a dropdown: <${element.tagName.toLowerCase()}>`};
				}
				const option = candidates.find((candidate) => {
					const label = (candidate.textContent || '').trim();
					const value = candidate.value
						|| candidate.getAttribute('data-value')
						|| candidate.getAttribute('value')
						|| '';
					return label === text || value === text;
				});
				if (!option) return {error: `Option not found: ${text}`};
				for (const candidate of candidates) candidate.setAttribute('aria-selected', 'false');
				option.setAttribute('aria-selected', 'true');
				option.click();
				element.dispatchEvent(new Event('input', {bubbles: true}));
				element.dispatchEvent(new Event('change', {bubbles: true}));
				return {selected: (option.textContent || '').trim()};
			}""",
			text,
		)
		if data.get('error'):
			return {'success': 'false', 'error': str(data['error'])}
		if data.get('native'):
			try:
				await locator.select_option(label=text)
			except Error:
				return {'success': 'false', 'error': f'Option not found: {text}'}
		return {'success': 'true', 'message': f'Selected option: {text}'}

	async def upload_file(self, node: EnhancedDOMTreeNode, file_path: str) -> None:
		await self._locator_for_node(node).set_input_files(file_path)

	@property
	def cdp_client(self) -> NoFakeCDPClient:
		return NoFakeCDPClient()

	def _raise_no_fake_cdp_boundary(self, capability: str) -> None:
		raise RuntimeError(_no_fake_cdp_message(capability))

	async def get_or_create_cdp_session(self, *args: Any, **kwargs: Any) -> None:
		self._raise_no_fake_cdp_boundary('Raw CDP sessions')

	async def start_tracing(self, *args: Any, **kwargs: Any) -> None:
		self._raise_no_fake_cdp_boundary('CDP tracing')

	async def start_profiling(self, *args: Any, **kwargs: Any) -> None:
		self._raise_no_fake_cdp_boundary('CDP profiling')

	async def start_coverage(self, *args: Any, **kwargs: Any) -> None:
		self._raise_no_fake_cdp_boundary('CDP coverage')

	async def get_element_by_index(self, index: int) -> EnhancedDOMTreeNode | None:
		return await self._get_fresh_node(index)

	async def get_dom_element_by_index(self, index: int) -> EnhancedDOMTreeNode | None:
		return await self.get_element_by_index(index)

	async def get_target_id_from_tab_id(self, tab_id: str) -> str:
		for index, tab in enumerate(await self.get_tabs()):
			if tab.target_id.endswith(tab_id) or str(index) == str(tab_id):
				return tab.target_id
		raise ValueError(f'No TargetID found ending in tab_id=...{tab_id}')

	async def highlight_interaction_element(self, node: EnhancedDOMTreeNode) -> None:
		locator = self._locator_for_node(node)
		await locator.evaluate(
			"""element => {
				document.querySelectorAll('[data-browser-use-camoufox-highlight]').forEach((highlighted) => {
					highlighted.style.outline = highlighted.dataset.browserUseCamoufoxPreviousOutline || '';
					highlighted.style.boxShadow = highlighted.dataset.browserUseCamoufoxPreviousBoxShadow || '';
					delete highlighted.dataset.browserUseCamoufoxPreviousOutline;
					delete highlighted.dataset.browserUseCamoufoxPreviousBoxShadow;
					highlighted.removeAttribute('data-browser-use-camoufox-highlight');
				});
				element.dataset.browserUseCamoufoxPreviousOutline = element.style.outline || '';
				element.dataset.browserUseCamoufoxPreviousBoxShadow = element.style.boxShadow || '';
				element.setAttribute('data-browser-use-camoufox-highlight', 'true');
				element.style.outline = '3px solid rgb(255, 152, 0)';
				element.style.boxShadow = '0 0 0 4px rgba(255, 152, 0, 0.25)';
			}"""
		)

	async def get_tabs(self) -> list[TabInfo]:
		if self._context is None:
			return []
		tabs = []
		for index, page in enumerate(self._context.pages):
			tabs.append(
				TabInfo(
					url=page.url,
					title=await page.title(),
					target_id=self._tab_target_id(index),
					parent_target_id=None,
				)
			)
		return tabs

	def _register_camoufox_event_handlers(self) -> None:
		self.event_bus.handlers['BrowserStartEvent'] = []
		self.event_bus.handlers['BrowserStopEvent'] = []
		self.event_bus.handlers['NavigateToUrlEvent'] = [self.on_NavigateToUrlEvent]
		self.event_bus.handlers['GoBackEvent'] = [self.on_GoBackEvent]
		self.event_bus.handlers['GoForwardEvent'] = [self.on_GoForwardEvent]
		self.event_bus.handlers['RefreshEvent'] = [self.on_RefreshEvent]
		self.event_bus.handlers['WaitEvent'] = [self.on_WaitEvent]
		self.event_bus.handlers['SwitchTabEvent'] = [self.on_SwitchTabEvent]
		self.event_bus.handlers['CloseTabEvent'] = [self.on_CloseTabEvent]
		self.event_bus.handlers['BrowserStateRequestEvent'] = [self.on_BrowserStateRequestEvent]
		self.event_bus.handlers['ClickElementEvent'] = [self.on_ClickElementEvent]
		self.event_bus.handlers['ClickCoordinateEvent'] = [self.on_ClickCoordinateEvent]
		self.event_bus.handlers['TypeTextEvent'] = [self.on_TypeTextEvent]
		self.event_bus.handlers['ScrollEvent'] = [self.on_ScrollEvent]
		self.event_bus.handlers['ScrollToTextEvent'] = [self.on_ScrollToTextEvent]
		self.event_bus.handlers['SendKeysEvent'] = [self.on_SendKeysEvent]
		self.event_bus.handlers['GetDropdownOptionsEvent'] = [self.on_GetDropdownOptionsEvent]
		self.event_bus.handlers['SelectDropdownOptionEvent'] = [self.on_SelectDropdownOptionEvent]
		self.event_bus.handlers['UploadFileEvent'] = [self.on_UploadFileEvent]
		self.event_bus.handlers['SaveStorageStateEvent'] = [self.on_SaveStorageStateEvent]
		self.event_bus.handlers['LoadStorageStateEvent'] = [self.on_LoadStorageStateEvent]

	def _record_navigation_url(self, url: str) -> None:
		if self._navigation_history_index >= 0 and self._navigation_history[self._navigation_history_index] == url:
			return
		self._navigation_history = self._navigation_history[: self._navigation_history_index + 1]
		self._navigation_history.append(url)
		self._navigation_history_index = len(self._navigation_history) - 1

	def _element_evidence_for_match(self, node_offsets: list[dict[str, Any]], match_index: int) -> dict[str, Any]:
		for node in node_offsets:
			if node['offset'] <= match_index < node['offset'] + node['length']:
				return node
		return {}

	def _tab_target_id(self, index: int) -> str:
		return f'camoufox-tab-{index:04d}'

	def _tab_target_matches(self, index: int, target_id: str | None) -> bool:
		if target_id is None:
			return False
		target = str(target_id)
		return target in {str(index), f'{index:04d}', self._tab_target_id(index)}

	async def _scroll_nearest_container(self, node: EnhancedDOMTreeNode, x_delta: int, y_delta: int) -> dict[str, Any]:
		locator = self._locator_for_node(node)
		return cast(
			dict[str, Any],
			await locator.evaluate(
				"""(element, delta) => {
				const metrics = (target) => {
					const isWindow = target === window;
					const width = isWindow ? document.documentElement.scrollWidth : target.scrollWidth;
					const height = isWindow ? document.documentElement.scrollHeight : target.scrollHeight;
					const clientWidth = isWindow ? window.innerWidth : target.clientWidth;
					const clientHeight = isWindow ? window.innerHeight : target.clientHeight;
					return {
						x: Math.round(isWindow ? window.scrollX : target.scrollLeft),
						y: Math.round(isWindow ? window.scrollY : target.scrollTop),
						max_x: Math.max(0, Math.round(width - clientWidth)),
						max_y: Math.max(0, Math.round(height - clientHeight)),
					};
				};
				const isBlockedByBoundary = (before) => (
					(delta.y > 0 && before.y >= before.max_y)
					|| (delta.y < 0 && before.y <= 0)
					|| (delta.x > 0 && before.x >= before.max_x)
					|| (delta.x < 0 && before.x <= 0)
				);
				const blocker = (before, after) => {
					if (before.x !== after.x || before.y !== after.y) return 'moved';
					return isBlockedByBoundary(before) ? 'already_at_boundary' : 'not_scrollable';
				};
				const canScroll = (candidate) => {
					if (!candidate) return false;
					const style = window.getComputedStyle(candidate);
					const overflowY = style.overflowY;
					const overflowX = style.overflowX;
					return (
					(
						delta.y !== 0
						&& /(auto|scroll|overlay)/.test(overflowY)
						&& candidate.scrollHeight > candidate.clientHeight
					)
					|| (
						delta.x !== 0
						&& /(auto|scroll|overlay)/.test(overflowX)
						&& candidate.scrollWidth > candidate.clientWidth
					)
					);
				};
				let container = element.parentElement;
				while (container && container !== document.body && !canScroll(container)) {
					container = container.parentElement;
				}
				const target = container && canScroll(container) ? container : window;
				const before = metrics(target);
				if (target === window) window.scrollBy(delta.x, delta.y);
				else target.scrollBy({left: delta.x, top: delta.y});
				const after = metrics(target);
				return {
					before,
					after,
					target_index: delta.targetIndex,
					target_type: target === window ? 'page' : 'container',
					blocker: blocker(before, after),
				};
			}""",
				{'x': x_delta, 'y': y_delta, 'targetIndex': node.node_id},
			),
		)

	async def _scroll_page_with_diagnostics(self, x_delta: int, y_delta: int) -> dict[str, Any]:
		page = await self._ensure_page()
		return cast(
			dict[str, Any],
			await page.evaluate(
				"""(delta) => {
				const metrics = () => ({
					x: Math.round(window.scrollX),
					y: Math.round(window.scrollY),
					max_x: Math.max(0, Math.round(document.documentElement.scrollWidth - window.innerWidth)),
					max_y: Math.max(0, Math.round(document.documentElement.scrollHeight - window.innerHeight)),
				});
				const before = metrics();
				window.scrollBy(delta.x, delta.y);
				const after = metrics();
				let blocker = 'moved';
				if (before.x === after.x && before.y === after.y) {
					const atBoundary = (
						(delta.y > 0 && before.y >= before.max_y)
						|| (delta.y < 0 && before.y <= 0)
						|| (delta.x > 0 && before.x >= before.max_x)
						|| (delta.x < 0 && before.x <= 0)
					);
					blocker = atBoundary ? 'already_at_boundary' : 'not_scrollable';
				}
				return {before, after, target_index: null, target_type: 'page', blocker};
			}""",
				{'x': x_delta, 'y': y_delta},
			),
		)

	async def _ensure_page(self, *, new_tab: bool = False) -> Page:
		if self._context is None:
			await self.start()
		assert self._context is not None
		if self._page is None or new_tab:
			self._page = await self._context.new_page()
		return self._page

	async def _ensure_context(self, browser: Browser | BrowserContext) -> BrowserContext:
		if hasattr(browser, 'new_context'):
			options = self._playwright_context_options()
			playwright_browser = cast(Browser, browser)
			try:
				context = await playwright_browser.new_context(**options)
			except Error as exc:
				har_options = sorted(key for key in options if key.startswith('record_har_'))
				video_options = sorted(key for key in options if key.startswith('record_video_'))
				recording_options = ', '.join(har_options or video_options)
				if recording_options:
					self._recording_rejected = True
					recording_type = 'HAR' if har_options else 'Video'
					raise RuntimeError(
						f'{recording_type} recording options were rejected by the Camoufox runtime '
						f'({recording_options}): {exc}'
					) from exc
				raise
			await self._apply_context_options(context)
			return context
		context = cast(BrowserContext, browser)
		self._reject_context_recording_options_for_reused_context()
		await self._apply_context_options(context)
		return context

	async def _ensure_context_started(self) -> BrowserContext:
		if self._context is None:
			await self.start()
		assert self._context is not None
		return self._context

	def _playwright_context_options(self) -> dict[str, Any]:
		options: dict[str, Any] = {}
		for source, target in [
			('accept_downloads', 'accept_downloads'),
			('record_har_content', 'record_har_content'),
			('record_har_mode', 'record_har_mode'),
			('record_har_path', 'record_har_path'),
			('record_video_dir', 'record_video_dir'),
			('record_video_size', 'record_video_size'),
			('geolocation', 'geolocation'),
			('permissions', 'permissions'),
			('storage_state', 'storage_state'),
		]:
			if source in self._context_options:
				options[target] = self._context_options[source]
		if 'headers' in self._context_options:
			options['extra_http_headers'] = self._context_options['headers']
		if 'record_har_path' in options:
			options['record_har_path'] = str(options['record_har_path'])
		if 'record_video_dir' in options:
			options['record_video_dir'] = str(options['record_video_dir'])
		if 'storage_state' in options:
			options['storage_state'] = self._clean_storage_state(options['storage_state'])
		return options

	def _reject_unsupported_profile_mappings(self, launch_options: dict[str, Any]) -> None:
		rejected = sorted(option for option in UNSUPPORTED_PROFILE_MAPPINGS if launch_options.get(option) is not None)
		if not rejected:
			return
		raise ValueError(
			'CamoufoxSession does not silently accept unsupported profile mappings '
			f'({", ".join(rejected)}). Use real Camoufox/Playwright equivalents when available; '
			'no fake CDP behavior is provided.'
		)

	def _reject_context_recording_options_for_reused_context(self) -> None:
		recording_options = sorted(
			key for key in self._context_options if key.startswith(('record_har_', 'record_video_'))
		)
		if recording_options:
			self._recording_rejected = True
			raise RuntimeError(
				'Recording options require creating a new Playwright browser context; '
				'Camoufox returned an existing context and rejected: ' + ', '.join(recording_options)
			)

	async def _apply_context_options(self, context: BrowserContext) -> None:
		for script in self._context_options.get('init_scripts', []):
			await context.add_init_script(script)
		if permissions := self._context_options.get('permissions'):
			await context.grant_permissions(permissions)

	def _download_target(self, suggested_filename: str) -> Path:
		downloads_path = Path(self._context_options.get('downloads_path') or Path.cwd())
		downloads_path.mkdir(parents=True, exist_ok=True)
		return downloads_path / suggested_filename

	def _clean_storage_state(self, storage_state: str | Path | dict[str, Any]) -> str | Path | dict[str, Any]:
		if not isinstance(storage_state, (str, Path)):
			return storage_state
		path = Path(storage_state)
		state = json.loads(path.read_text())
		for cookie in state.get('cookies', []):
			if not cookie.get('path'):
				cookie['path'] = '/'
			if 'url' not in cookie and not cookie.get('domain'):
				cookie['url'] = 'file:///'
		clean_path = path.with_suffix('.camoufox.json')
		clean_path.write_text(json.dumps(state))
		return clean_path

	async def _get_dom_state(self) -> SerializedDOMState:
		page = await self._ensure_page()
		elements = await self._extract_interactive_elements(page)
		selector_map: dict[int, EnhancedDOMTreeNode] = {}
		self._selector_targets.clear()
		for element in elements:
			index = len(selector_map) + 1
			target = self._normalize_selector_target(element, index)
			self._selector_targets[index] = target
			attributes = self._normalize_dom_attributes(element.get('attributes'))
			attributes['data-browser-use-camoufox-selector'] = str(target['selector'])
			attributes['data-browser-use-camoufox-ordinal'] = str(target['ordinal'])
			attributes['data-browser-use-camoufox-disabled'] = str(bool(element.get('is_disabled', False))).lower()
			attributes['data-browser-use-camoufox-frame'] = str(target['frame_id'])
			if not element.get('is_interactive', True):
				attributes[OBSERVABLE_ELEMENT_ATTRIBUTE] = 'true'
			if target['frame_url']:
				attributes['data-browser-use-camoufox-frame-url'] = str(target['frame_url'])
			if target['shadow_root_type']:
				attributes['data-browser-use-camoufox-shadow-root'] = str(target['shadow_root_type'])
			evidence = self._semantic_evidence_for_node(element, attributes)
			if evidence:
				attributes[SEMANTIC_EVIDENCE_ATTRIBUTE] = evidence
			selector_map[index] = self._node_from_payload(element, index, attributes)
		self._cached_selector_map = selector_map
		return SerializedDOMState(_root=self._selector_tree_root(selector_map), selector_map=selector_map)

	def _selector_tree_root(self, selector_map: dict[int, EnhancedDOMTreeNode]) -> SimplifiedNode | None:
		if not selector_map:
			return None
		root_node = EnhancedDOMTreeNode(
			node_id=0,
			backend_node_id=0,
			node_type=NodeType.DOCUMENT_NODE,
			node_name='#document',
			node_value='',
			attributes={},
			is_scrollable=None,
			is_visible=True,
			absolute_position=None,
			target_id='camoufox',
			frame_id='main',
			session_id=None,
			content_document=None,
			shadow_root_type=None,
			shadow_roots=None,
			parent_node=None,
			children_nodes=list(selector_map.values()),
			ax_node=None,
			snapshot_node=None,
		)
		root = SimplifiedNode(original_node=root_node, children=[])
		for index, node in selector_map.items():
			node.backend_node_id = index
			node.parent_node = root_node
			children = []
			if node.node_value.strip():
				children.append(SimplifiedNode(original_node=self._text_node_for(node), children=[]))
			root.children.append(SimplifiedNode(original_node=node, children=children, is_interactive=True))
		return root

	def _text_node_for(self, parent: EnhancedDOMTreeNode) -> EnhancedDOMTreeNode:
		return EnhancedDOMTreeNode(
			node_id=parent.node_id * 1000,
			backend_node_id=parent.backend_node_id * 1000,
			node_type=NodeType.TEXT_NODE,
			node_name='#text',
			node_value=parent.node_value,
			attributes={},
			is_scrollable=None,
			is_visible=True,
			absolute_position=parent.absolute_position,
			target_id=parent.target_id,
			frame_id=parent.frame_id,
			session_id=parent.session_id,
			content_document=None,
			shadow_root_type=None,
			shadow_roots=None,
			parent_node=parent,
			children_nodes=None,
			ax_node=None,
			snapshot_node=parent.snapshot_node,
		)

	async def _get_fresh_node(self, index: int) -> EnhancedDOMTreeNode | None:
		await self._get_dom_state()
		return self._cached_selector_map.get(index)

	async def _relocalize_action_node(self, node: EnhancedDOMTreeNode) -> EnhancedDOMTreeNode:
		await self._get_dom_state()
		signature = self._action_node_signature(node)
		if signature is None:
			return self._cached_selector_map.get(node.node_id, node)
		matches = [
			candidate
			for candidate in self._cached_selector_map.values()
			if self._action_node_signature(candidate) == signature
		]
		if not matches:
			raise RuntimeError(f'Element {node.node_id} relocalization unavailable after DOM refresh.')
		actionable_matches = [
			candidate
			for candidate in matches
			if candidate.attributes.get('data-browser-use-camoufox-disabled') != 'true'
			and candidate.attributes.get(OBSERVABLE_ELEMENT_ATTRIBUTE) != 'true'
		]
		if len(actionable_matches) != 1:
			raise RuntimeError(
				f'Element {node.node_id} relocalization ambiguous or blocked by safety checks: '
				f'{len(matches)} candidate(s), {len(actionable_matches)} actionable.'
			)
		return actionable_matches[0]

	def _action_node_signature(self, node: EnhancedDOMTreeNode) -> tuple[str, str, str, str, str] | None:
		selector = node.attributes.get('data-browser-use-camoufox-selector')
		frame = node.attributes.get('data-browser-use-camoufox-frame', 'main')
		frame_url = node.attributes.get('data-browser-use-camoufox-frame-url', '')
		text = node.node_value.strip()
		if not selector or not text:
			return None
		return (node.tag_name.upper(), selector, frame, frame_url, text)

	def _missing_index_result(self, index: int) -> ActionResult:
		url = self._page.url if self._page is not None else 'about:blank'
		count = len(self._cached_selector_map)
		return ActionResult(
			error=f'Element index {index} is not available at {url}. Refreshed selector count: {count}.'
		)

	def _locator_for_node(self, node: EnhancedDOMTreeNode):
		page = self._page
		if page is None:
			raise RuntimeError('Camoufox page is not started.')
		target = self._selector_targets.get(node.node_id)
		selector = target.get('selector') if target else node.attributes.get('data-browser-use-camoufox-selector')
		ordinal = target.get('ordinal') if target else node.attributes.get('data-browser-use-camoufox-ordinal')
		if selector is None or ordinal is None:
			raise RuntimeError(f'Camoufox selector metadata is missing for node {node.node_id}.')
		frame_id = target.get('frame_id') if target else node.attributes.get('data-browser-use-camoufox-frame')
		frame_url = target.get('frame_url') if target else node.attributes.get('data-browser-use-camoufox-frame-url')
		if frame_id and str(frame_id) != 'main':
			frame = self._frame_for_target(page, str(frame_id), str(frame_url or ''))
			if frame is None:
				raise RuntimeError(f'Camoufox frame is no longer available for node {node.node_id}: {frame_id}')
			return frame.locator(str(selector)).nth(int(ordinal))
		return page.locator(str(selector)).nth(int(ordinal))

	def _click_error_message(self, node: EnhancedDOMTreeNode, exc: Error) -> str:
		selector = node.attributes.get('data-browser-use-camoufox-selector', '<unknown>')
		ordinal = node.attributes.get('data-browser-use-camoufox-ordinal', '<unknown>')
		text = (node.node_value or node.attributes.get('aria-label') or node.attributes.get('title') or '').strip()
		state = node.attributes.get('data-state')
		details = [
			f'Camoufox click failed after {CLICK_TIMEOUT_MS}ms',
			f'node={node.node_id}',
			f'selector={selector}',
			f'ordinal={ordinal}',
			f'tag={node.tag_name}',
		]
		if state:
			details.append(f'data-state={state}')
		if text:
			details.append(f'text={text[:120]}')
		details.append(f'playwright_error={str(exc).splitlines()[0]}')
		return '; '.join(details)

	async def _capture_click_state(self, node: EnhancedDOMTreeNode) -> dict[str, Any]:
		page = await self._ensure_page()
		target_attributes: dict[str, str] = {}
		try:
			raw_attributes = await self._locator_for_node(node).evaluate(
				"""(element) => Object.fromEntries(
					Array.from(element.attributes).map((attribute) => [attribute.name, attribute.value])
				)"""
			)
			target_attributes = self._safe_attribute_snapshot(raw_attributes)
		except Error:
			target_attributes = {}
		body_metrics = await page.locator('body').evaluate(
			"""(body) => ({
				text: (body.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 400),
				count: body.querySelectorAll('*').length,
			})"""
		)
		return {
			'url': page.url,
			'title': await page.title(),
			'dom_count': int(body_metrics.get('count') or 0) if isinstance(body_metrics, dict) else 0,
			'visible_text': str(body_metrics.get('text') or '') if isinstance(body_metrics, dict) else '',
			'target_attributes': target_attributes,
		}

	def _click_change_diagnostics(self, before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
		before_text = str(before.get('visible_text') or '')
		after_text = str(after.get('visible_text') or '')
		before_attrs = cast(dict[str, str], before.get('target_attributes') or {})
		after_attrs = cast(dict[str, str], after.get('target_attributes') or {})
		return {
			'url_changed': before.get('url') != after.get('url'),
			'url': {
				'before': before.get('url'),
				'after': after.get('url'),
				'changed': before.get('url') != after.get('url'),
			},
			'title': {
				'before': before.get('title'),
				'after': after.get('title'),
				'changed': before.get('title') != after.get('title'),
			},
			'dom_count': {
				'before': before.get('dom_count'),
				'after': after.get('dom_count'),
				'changed': before.get('dom_count') != after.get('dom_count'),
			},
			'visible_text_change': {
				'changed': before_text != after_text,
				'before_excerpt': before_text[:200],
				'after_excerpt': after_text[:200],
			},
			'target_attributes': {
				'before': before_attrs,
				'after': after_attrs,
				'changed': before_attrs != after_attrs,
			},
		}

	def _safe_attribute_snapshot(self, attributes: Any) -> dict[str, str]:
		if not isinstance(attributes, dict):
			return {}
		safe_attributes: dict[str, str] = {}
		for key, value in attributes.items():
			name = str(key)
			normalized_name = name.lower()
			if any(marker in normalized_name for marker in SENSITIVE_ATTRIBUTE_MARKERS):
				continue
			safe_attributes[name] = re.sub(r'\s+', ' ', str(value)).strip()[:MAX_SAFE_ATTRIBUTE_VALUE_LENGTH]
		return safe_attributes

	def _classify_keyboard_input(self, keys: str) -> Literal['text', 'press', 'invalid']:
		if not keys:
			return 'invalid'
		if keys in PLAYWRIGHT_SPECIAL_KEYS:
			return 'press'
		if '+' in keys:
			parts = keys.split('+')
			if any(not part for part in parts):
				return 'invalid'
			return 'press'
		if len(keys) == 1 and not keys.isprintable():
			return 'invalid'
		if len(keys) == 1 or any(character in keys for character in ('\n', '\r', '\t')) or keys.isprintable():
			return 'text'
		return 'invalid'

	async def _prepare_keyboard_focus(self, page: Page) -> None:
		selector = await page.evaluate(
			"""() => {
			const editableSelector = [
				'input', 'textarea', 'select', '[contenteditable=""]', '[contenteditable="true"]', '[role="textbox"]'
			].join(', ');
			const active = document.activeElement;
			if (active && active.matches(editableSelector)) return null;
			const selectors = [
				'[role=application]', '[role=main]', 'main', 'canvas', '#app', '#app-root', '[data-app-root]', 'body'
			];
			const target = selectors.map((selector) => document.querySelector(selector)).find(Boolean);
			if (!target || target === document.body) return null;
			if (!target.hasAttribute('tabindex') && target !== document.body) target.setAttribute('tabindex', '0');
			if (target.id) return `#${CSS.escape(target.id)}`;
			target.setAttribute('data-browser-use-camoufox-focus-target', 'true');
			return '[data-browser-use-camoufox-focus-target="true"]';
			}"""
		)
		if selector:
			await page.locator(str(selector)).focus()

	async def _active_element_diagnostics(self, page: Page) -> dict[str, str]:
		return cast(
			dict[str, str],
			await page.evaluate(
				"""() => {
				const element = document.activeElement || document.body;
				const clean = (value) => (value || '').replace(/\\s+/g, ' ').trim().slice(0, 120);
				return {
					tag: clean(element.tagName ? element.tagName.toLowerCase() : ''),
					role: clean(element.getAttribute('role')),
					id: clean(element.id),
					class: clean(element.className && typeof element.className === 'string' ? element.className : ''),
					text_excerpt: clean(element.innerText || element.textContent),
					label_excerpt: clean(
						element.getAttribute('aria-label')
						|| element.getAttribute('title')
						|| element.getAttribute('placeholder')
						|| ''
					),
				};
				}"""
			),
		)

	def _frame_for_target(self, page: Page, frame_id: str, frame_url: str):
		for frame_index, frame in enumerate(page.frames):
			candidate_id = 'main' if frame == page.main_frame else f'frame-{frame_index}'
			if candidate_id == frame_id and (not frame_url or frame.url == frame_url):
				return frame
		return None

	async def _extract_interactive_elements(self, page: Page) -> list[dict[str, Any]]:
		elements: list[dict[str, Any]] = []
		for frame_index, frame in enumerate(page.frames):
			frame_elements = await frame.evaluate(
				"""(args) => {
				const selectorList = [
					'button', 'a[href]', 'input', 'textarea', 'select',
					'[contenteditable=""]', '[contenteditable="true"]', '[role="button"]',
					'[role="link"]', '[role="textbox"]', '[role="checkbox"]', '[role="radio"]',
					'[role="listbox"]', '[role="option"]', '[role="menu"]', '[role="menuitem"]', '[tabindex]',
				];
				const attributeNames = [
					'id', 'class', 'name', 'type', 'role', 'href', 'title', 'value', 'placeholder', 'alt',
					'aria-label', 'aria-expanded', 'aria-checked', 'aria-selected', 'aria-disabled',
					'disabled', 'readonly', 'required', 'contenteditable', 'tabindex',
				];
				const sensitiveAttributeMarkers = args.sensitiveAttributeMarkers || [];
				const normalizeText = (value) => (value || '').replace(/\\s+/g, ' ').trim();
				const isSensitiveAttribute = (name) => {
					const normalized = String(name || '').toLowerCase();
					return sensitiveAttributeMarkers.some((marker) => normalized.includes(marker));
				};
				const safeAttributeValue = (name, value) => {
					if (isSensitiveAttribute(name)) return null;
					return normalizeText(value).slice(0, args.maxAttributeValueLength);
				};
				const semanticTags = new Set([
					'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li', 'dt', 'dd', 'summary', 'figcaption',
					'blockquote', 'caption', 'td', 'th', 'main', 'article', 'section', 'ul', 'ol', 'table',
				]);
				const semanticRoles = new Set([
					'alert', 'article', 'cell', 'columnheader', 'gridcell', 'heading', 'note', 'rowheader',
					'status', 'tabpanel', 'main', 'list', 'grid', 'table', 'region',
				]);
				const centralContainers = [
					'main', '[role="main"]', 'article', '[role="article"]', '[role="list"]',
					'ul', 'ol', '[role="grid"]', 'table',
				].join(', ');
				const repeatedChromeContainers = [
					'nav', 'aside', 'header', 'footer', '[role="navigation"]', '[aria-label*="filter" i]',
				].join(', ');
				const ordinals = new Map();
				const shadowHostSelector = '*';
				const elementPayload = (element, shadowRootType = null) => {
					const tagName = element.tagName.toLowerCase();
					const inCentralContent = Boolean(element.closest(centralContainers));
					const inRepeatedChrome = Boolean(element.closest(repeatedChromeContainers));
					const isInteractive = selectorList.some((candidate) => element.matches(candidate));
					const matchedSelector = selectorList.find((candidate) => element.matches(candidate)) || tagName;
					let stableSelector = matchedSelector;
					if (element.id) {
						stableSelector = `#${CSS.escape(element.id)}`;
					} else if (element.getAttribute('data-testid')) {
						stableSelector = `[data-testid="${CSS.escape(element.getAttribute('data-testid'))}"]`;
					} else if (element.getAttribute('name')) {
						stableSelector = `${tagName}[name="${CSS.escape(element.getAttribute('name'))}"]`;
					} else if (element.getAttribute('aria-label')) {
						const ariaLabel = CSS.escape(element.getAttribute('aria-label'));
						stableSelector = `${matchedSelector}[aria-label="${ariaLabel}"]`;
					}
					const ordinal = ordinals.get(stableSelector) || 0;
					ordinals.set(stableSelector, ordinal + 1);
					const rect = element.getBoundingClientRect();
					const style = window.getComputedStyle(element);
					const attributes = {};
					for (const name of attributeNames) {
						if (element.hasAttribute(name)) {
							const value = safeAttributeValue(name, element.getAttribute(name) || '');
							if (value !== null) attributes[name] = value;
						}
					}
					for (const attr of Array.from(element.attributes)) {
						const value = safeAttributeValue(attr.name, attr.value);
						if (
							value !== null
							&&
							attr.name.startsWith('data-')
							&& attr.name.length <= 40
							&& attr.value.length <= 120
							&& Object.keys(attributes).filter((name) => name.startsWith('data-')).length < 8
						) {
							attributes[attr.name] = value;
						}
					}
					const disabled = element.disabled === true || element.getAttribute('aria-disabled') === 'true';
					const visible = rect.width > 0 && rect.height > 0
						&& style.visibility !== 'hidden' && style.display !== 'none';
					const text = normalizeText(
						element.innerText || element.value || element.getAttribute('aria-label') || ''
					)
						.slice(0, 200);
					const role = element.getAttribute('role') || '';
					const hasObservableState = Object.keys(attributes).some((name) => (
						name.startsWith('aria-') || name.startsWith('data-')
					));
					const isObservable = isInteractive || (
						text
						&& (
							semanticTags.has(tagName)
							|| semanticRoles.has(role)
							|| hasObservableState
							|| element.getAttribute('aria-label')
						)
					);
					return {
						tagName: element.nodeName,
						text,
						attributes, selector: stableSelector, ordinal, is_visible: visible, is_disabled: disabled,
						is_interactive: isInteractive && !disabled, is_observable: isObservable,
						frame_id: args.frameId, frame_url: args.frameUrl,
						shadow_root_type: shadowRootType,
						priority:
							(inCentralContent ? 1000 : 0)
							- (inRepeatedChrome ? 100 : 0)
							+ (isInteractive ? 10 : 0),
						rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
					};
				};
				const domRoot = document.body || document;
				const elements = Array.from(domRoot.querySelectorAll('*'))
					.map((element, documentOrder) => ({...elementPayload(element), documentOrder}))
					.filter((element) => element.is_visible && element.is_observable);
				for (const host of Array.from(document.querySelectorAll(shadowHostSelector))) {
					if (host.shadowRoot) {
						const shadowElements = Array.from(host.shadowRoot.querySelectorAll('*'))
							.map((element, documentOrder) => ({...elementPayload(element, 'open'), documentOrder}))
							.filter((element) => element.is_visible && element.is_observable);
						elements.push(...shadowElements);
					} else if (host.localName.includes('-')) {
						const payload = elementPayload(host, 'closed');
						if (payload.is_visible) elements.push(payload);
					}
				}
				return elements
					.map((element, index) => ({...element, originalOrder: element.documentOrder ?? index}))
					.sort((left, right) => (
						(right.priority - left.priority) || (left.originalOrder - right.originalOrder)
					))
					.slice(0, 300)
					.sort((left, right) => left.originalOrder - right.originalOrder);
			}""",
				{
					'frameId': 'main' if frame == page.main_frame else f'frame-{frame_index}',
					'frameUrl': '' if frame == page.main_frame else frame.url,
					'maxAttributeValueLength': MAX_SAFE_ATTRIBUTE_VALUE_LENGTH,
					'sensitiveAttributeMarkers': list(SENSITIVE_ATTRIBUTE_MARKERS),
				},
			)
			if isinstance(frame_elements, list):
				elements.extend(element for element in frame_elements if isinstance(element, dict))
		return elements

	def _normalize_selector_target(self, element: dict[str, Any], fallback_index: int) -> dict[str, Any]:
		selector = str(element.get('selector') or element.get('tagName') or '*')
		ordinal = element.get('ordinal')
		if not isinstance(ordinal, int):
			ordinal = fallback_index - 1
		return {
			'selector': selector,
			'ordinal': max(ordinal, 0),
			'frame_id': str(element.get('frame_id') or 'main'),
			'frame_url': str(element.get('frame_url') or ''),
			'shadow_root_type': str(element.get('shadow_root_type') or ''),
		}

	def _normalize_dom_attributes(self, attributes: Any) -> dict[str, str]:
		if not isinstance(attributes, dict):
			return {}
		return {str(key): str(value) for key, value in attributes.items() if value is not None}

	def _semantic_evidence_for_node(self, element: dict[str, Any], attributes: dict[str, str]) -> str:
		parts = []
		text = re.sub(r'\s+', ' ', str(element.get('text') or '')).strip()
		if text:
			parts.append(f'text={text}')
		for name in ('data-testid', 'data-state', 'aria-label', 'title', 'placeholder', 'alt', 'name', 'type', 'role'):
			value = attributes.get(name)
			if value:
				parts.append(f'{name}={value}')
		evidence = '; '.join(parts)
		if len(evidence) <= MAX_SEMANTIC_EVIDENCE_LENGTH:
			return evidence
		return evidence[: MAX_SEMANTIC_EVIDENCE_LENGTH - 1].rstrip() + '…'

	def _node_from_payload(
		self, payload: dict[str, Any], index: int, attributes: dict[str, str]
	) -> EnhancedDOMTreeNode:
		rect = payload['rect']
		bounds = DOMRect(x=rect['x'], y=rect['y'], width=rect['width'], height=rect['height'])
		shadow_root_type = cast(Literal['user-agent', 'open', 'closed'] | None, payload.get('shadow_root_type') or None)
		return EnhancedDOMTreeNode(
			node_id=index,
			backend_node_id=index,
			node_type=NodeType.ELEMENT_NODE,
			node_name=str(payload['tagName']),
			node_value=str(payload.get('text') or ''),
			attributes=attributes,
			is_scrollable=None,
			is_visible=bool(payload.get('is_visible', True)),
			absolute_position=bounds,
			target_id='camoufox',
			frame_id=str(payload.get('frame_id') or 'main'),
			session_id=None,
			content_document=None,
			shadow_root_type=shadow_root_type,
			shadow_roots=None,
			parent_node=None,
			children_nodes=None,
			ax_node=None,
			snapshot_node=EnhancedSnapshotNode(
				is_clickable=bool(payload.get('is_interactive', True)) and not bool(payload.get('is_disabled', False)),
				cursor_style=None,
				bounds=bounds,
				clientRects=bounds,
				scrollRects=None,
				computed_styles=None,
				paint_order=None,
				stacking_contexts=None,
			),
		)

	def _stringify_js_result(self, value: Any) -> str:
		if isinstance(value, BaseModel):
			return value.model_dump_json()
		if isinstance(value, (dict, list)):
			return json.dumps(value, ensure_ascii=False)
		return str(value)
