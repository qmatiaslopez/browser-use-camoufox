from pathlib import Path

import pytest
from browser_use import Agent
from browser_use.browser.events import (
	BrowserStateRequestEvent,
	CloseTabEvent,
	NavigateToUrlEvent,
	SwitchTabEvent,
)
from browser_use.llm.views import ChatInvokeCompletion

from browser_use_camoufox import CamoufoxSession


class StaticLLM:
	model = 'static-test'

	@property
	def provider(self) -> str:
		return 'test'

	@property
	def name(self) -> str:
		return self.model

	async def ainvoke(self, messages, output_format=None, **kwargs):
		return ChatInvokeCompletion(completion='done')


@pytest.mark.anyio
async def test_agent_accepts_camoufox_session_startup_navigation_and_tabs(tmp_path: Path):
	fixture = tmp_path / 'agent.html'
	fixture.write_text('<html><head><title>Agent Camoufox</title></head><body>Ready</body></html>')

	session = CamoufoxSession(headless=True)
	agent = Agent(task='Inspect page', llm=StaticLLM(), browser_session=session)

	try:
		await agent.browser_session.start()
		await agent.browser_session.event_bus.dispatch(NavigateToUrlEvent(url=fixture.as_uri()))
		tabs = await agent.browser_session.get_tabs()

		assert await agent.browser_session.get_current_page_url() == fixture.as_uri()
		assert await agent.browser_session.get_current_page_title() == 'Agent Camoufox'
		assert len(tabs) == 1
		assert tabs[0].url == fixture.as_uri()
		assert agent.browser_session.cdp_url is None
		assert agent.browser_session._cdp_client_root is None
	finally:
		await agent.browser_session.stop()


@pytest.mark.anyio
async def test_camoufox_session_event_routing_handles_new_tabs_and_switching(tmp_path: Path):
	first = tmp_path / 'first.html'
	second = tmp_path / 'second.html'
	first.write_text('<html><head><title>First</title></head><body>First</body></html>')
	second.write_text('<html><head><title>Second</title></head><body>Second</body></html>')

	session = CamoufoxSession(headless=True)

	try:
		await session.start()
		await session.event_bus.dispatch(NavigateToUrlEvent(url=first.as_uri()))
		await session.event_bus.dispatch(NavigateToUrlEvent(url=second.as_uri(), new_tab=True))

		tabs = await session.get_tabs()
		assert [tab.title for tab in tabs] == ['First', 'Second']
		assert await session.get_current_page_title() == 'Second'
		assert tabs[0].target_id.endswith('0000')
		assert tabs[1].target_id.endswith('0001')

		await session.event_bus.dispatch(SwitchTabEvent(target_id=tabs[0].target_id[-4:]))
		assert await session.get_current_page_title() == 'First'
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_camoufox_session_event_routing_handles_state_requests_and_tab_close(tmp_path: Path):
	first = tmp_path / 'first.html'
	second = tmp_path / 'second.html'
	first.write_text('<html><head><title>First</title></head><body>First</body></html>')
	second.write_text('<html><head><title>Second</title></head><body>Second</body></html>')

	session = CamoufoxSession(headless=True)

	try:
		await session.start()
		await session.event_bus.dispatch(NavigateToUrlEvent(url=first.as_uri()))
		await session.event_bus.dispatch(NavigateToUrlEvent(url=second.as_uri(), new_tab=True))

		state_event = session.event_bus.dispatch(BrowserStateRequestEvent(include_dom=False, include_screenshot=False))
		await state_event
		state = await state_event.event_result()
		assert state.url == second.as_uri()
		assert state.title == 'Second'
		assert [tab.title for tab in state.tabs] == ['First', 'Second']
		assert state.dom_state.selector_map == {}

		await session.event_bus.dispatch(CloseTabEvent(target_id='0001'))
		tabs = await session.get_tabs()

		assert len(tabs) == 1
		assert tabs[0].title == 'First'
		assert await session.get_current_page_title() == 'First'
	finally:
		await session.stop()
