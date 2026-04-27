from browser_use_camoufox.compat.detector import (
	CompatibilityRequirement,
	check_browser_use_compatibility,
)


def test_detector_reports_installed_browser_use_version():
	result = check_browser_use_compatibility()

	assert result.installed_version == '0.12.6'
	assert result.target_version == '0.12.6'


def test_detector_accepts_required_browser_use_internals():
	result = check_browser_use_compatibility()

	assert result.ok is True
	assert result.missing_requirements == ()
	assert {requirement.label for requirement in result.requirements} >= {
		'browser_use.Agent',
		'browser_use.browser.BrowserSession.start',
		'browser_use.browser.BrowserSession.stop',
		'browser_use.tools.Tools.action',
		'browser_use.browser.events.BrowserStartEvent',
		'browser_use.browser.events.BrowserStopEvent',
		'browser_use.browser.events.NavigateToUrlEvent',
		'browser_use.browser.events.BrowserStateRequestEvent',
		'browser_use.browser.events.SwitchTabEvent',
		'browser_use.browser.events.CloseTabEvent',
		'browser_use.mcp.server.BrowserUseServer',
	}


def test_detector_rejects_unknown_browser_use_version():
	result = check_browser_use_compatibility(installed_version='99.0.0')

	assert result.ok is False
	assert result.version_supported is False
	assert 'unsupported browser-use version 99.0.0' in result.errors


def test_detector_reports_missing_required_internal():
	result = check_browser_use_compatibility(
		requirements=(
			CompatibilityRequirement(
				label='missing internal',
				module='browser_use.missing',
				attribute_path=('Nope',),
			),
		)
	)

	assert result.ok is False
	assert result.missing_requirements == ('missing internal',)
