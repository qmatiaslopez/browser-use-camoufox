from browser_use.browser.events import (
	BrowserStartEvent,
	BrowserStateRequestEvent,
	BrowserStopEvent,
	CloseTabEvent,
	NavigateToUrlEvent,
	SwitchTabEvent,
)

from browser_use_camoufox import CamoufoxSession


def test_camoufox_session_replaces_cdp_start_stop_handlers_with_playwright_event_routes():
	session = CamoufoxSession(headless=True)

	assert session.event_bus.handlers[BrowserStartEvent.__name__] == []
	assert session.event_bus.handlers[BrowserStopEvent.__name__] == []
	assert session.event_bus.handlers[NavigateToUrlEvent.__name__] == [session.on_NavigateToUrlEvent]
	assert session.event_bus.handlers[SwitchTabEvent.__name__] == [session.on_SwitchTabEvent]
	assert session.event_bus.handlers[CloseTabEvent.__name__] == [session.on_CloseTabEvent]
	assert session.event_bus.handlers[BrowserStateRequestEvent.__name__] == [session.on_BrowserStateRequestEvent]
	assert session._cdp_client_root is None
