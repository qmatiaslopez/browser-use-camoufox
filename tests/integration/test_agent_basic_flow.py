from pathlib import Path

import pytest
from browser_use import Agent
from browser_use.browser.events import BrowserStateRequestEvent
from browser_use.llm.views import ChatInvokeCompletion, ChatInvokeUsage
from browser_use.tools.service import Tools

from browser_use_camoufox import CamoufoxSession


class ScriptedLLM:
	model = 'scripted-test'
	model_name = model

	def __init__(self):
		self._agent = None
		self.calls = 0

	@property
	def provider(self) -> str:
		return 'test'

	@property
	def name(self) -> str:
		return self.model

	async def ainvoke(self, messages, output_format=None, **kwargs):
		self.calls += 1
		if self.calls == 1:
			action = {'click': {'index': 1}}
			completion = output_format(
				evaluation_previous_goal='Started local smoke task',
				memory='Clicked the local fixture button by visible DOM index',
				next_goal='Finish after clicking the page button',
				action=[action],
			)
		else:
			action = {'done': {'text': 'Verified local Camoufox agent smoke fixture.', 'success': True}}
			completion = output_format(
				evaluation_previous_goal='Verified the local fixture content',
				memory='Local fixture contains Camoufox agent smoke text',
				next_goal='Done',
				action=[action],
			)
		return ChatInvokeCompletion(
			completion=completion,
			usage=ChatInvokeUsage(
				prompt_tokens=0,
				prompt_cached_tokens=None,
				prompt_cache_creation_tokens=None,
				prompt_image_tokens=None,
				completion_tokens=0,
				total_tokens=0,
			),
		)


@pytest.mark.anyio
async def test_browser_use_tools_click_type_scroll_and_send_keys(tmp_path: Path):
	fixture = tmp_path / 'flow.html'
	fixture.write_text(
		"""
		<html>
			<head><title>Tool flow</title></head>
			<body style="height: 1800px">
				<button id="click-me" onclick="this.textContent = 'Clicked'">Click me</button>
				<input id="name" />
				<div style="margin-top: 1400px">Bottom</div>
			</body>
		</html>
		"""
	)

	session = CamoufoxSession(headless=True)
	tools = Tools()

	try:
		await session.start()
		await session.navigate_to(fixture.as_uri())
		state_event = session.event_bus.dispatch(BrowserStateRequestEvent(include_dom=True, include_screenshot=False))
		await state_event
		await state_event.event_result()

		click_result = await tools.registry.execute_action('click', {'index': 1}, browser_session=session)
		type_result = await tools.registry.execute_action('input', {'index': 2, 'text': 'Ada'}, browser_session=session)
		scroll_result = await tools.registry.execute_action(
			'scroll', {'down': True, 'num_pages': 1}, browser_session=session
		)
		send_keys_result = await tools.registry.execute_action('send_keys', {'keys': 'Enter'}, browser_session=session)

		page = await session.get_current_page()
		assert click_result.error is None
		assert type_result.error is None
		assert scroll_result.error is None
		assert send_keys_result.error is None
		assert await page.locator('#click-me').text_content() == 'Clicked'
		assert await page.locator('#name').input_value() == 'Ada'
		assert await page.evaluate('window.scrollY') > 0
	finally:
		await session.stop()


@pytest.mark.anyio
async def test_agent_run_completes_local_task_through_camoufox_session(tmp_path: Path):
	fixture = tmp_path / 'agent-run.html'
	fixture.write_text(
		"""
		<html>
			<head><title>Agent run smoke</title></head>
			<body>
				<button id="agent-button" onclick="this.textContent = 'Clicked by agent'">
					Camoufox agent smoke fixture
				</button>
			</body>
		</html>
		"""
	)

	llm = ScriptedLLM()
	session = CamoufoxSession(headless=True)
	agent = Agent(
		task=f'Open {fixture.as_uri()} and verify the Camoufox agent smoke text.',
		llm=llm,
		browser_session=session,
		use_vision=False,
		use_judge=False,
		enable_planning=False,
		initial_actions=[{'navigate': {'url': fixture.as_uri(), 'new_tab': False}}],
	)
	llm._agent = agent

	try:
		history = await agent.run(max_steps=3)

		assert history.is_done()
		assert history.is_successful()
		assert llm.calls == 2
		assert await session.get_current_page_url() == fixture.as_uri()
		assert await session.get_current_page_title() == 'Agent run smoke'
		page = await session.get_current_page()
		assert await page.locator('#agent-button').text_content() == 'Clicked by agent'
	finally:
		await session.stop()
