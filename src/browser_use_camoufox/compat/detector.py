from collections.abc import Sequence
from dataclasses import dataclass
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from browser_use_camoufox.diagnostics import TARGET_BROWSER_USE_VERSION


@dataclass(frozen=True)
class CompatibilityRequirement:
	label: str
	module: str
	attribute_path: tuple[str, ...]


@dataclass(frozen=True)
class CheckedRequirement:
	label: str
	ok: bool
	error: str | None = None


@dataclass(frozen=True)
class CompatibilityResult:
	target_version: str
	installed_version: str | None
	version_supported: bool
	requirements: tuple[CheckedRequirement, ...]
	errors: tuple[str, ...]

	@property
	def ok(self) -> bool:
		return self.version_supported and not self.errors and not self.missing_requirements

	@property
	def missing_requirements(self) -> tuple[str, ...]:
		return tuple(requirement.label for requirement in self.requirements if not requirement.ok)


REQUIRED_INTERNALS: tuple[CompatibilityRequirement, ...] = (
	CompatibilityRequirement('browser_use.Agent', 'browser_use', ('Agent',)),
	CompatibilityRequirement('browser_use.browser.BrowserSession', 'browser_use.browser', ('BrowserSession',)),
	CompatibilityRequirement(
		'browser_use.browser.BrowserSession.start', 'browser_use.browser', ('BrowserSession', 'start')
	),
	CompatibilityRequirement(
		'browser_use.browser.BrowserSession.stop', 'browser_use.browser', ('BrowserSession', 'stop')
	),
	CompatibilityRequirement('browser_use.tools.Tools', 'browser_use.tools.service', ('Tools',)),
	CompatibilityRequirement('browser_use.tools.Tools.action', 'browser_use.tools.service', ('Tools', 'action')),
	CompatibilityRequirement('browser_use.tools.Tools.act', 'browser_use.tools.service', ('Tools', 'act')),
	CompatibilityRequirement(
		'browser_use.browser.events.BrowserStartEvent', 'browser_use.browser.events', ('BrowserStartEvent',)
	),
	CompatibilityRequirement(
		'browser_use.browser.events.BrowserStopEvent', 'browser_use.browser.events', ('BrowserStopEvent',)
	),
	CompatibilityRequirement(
		'browser_use.browser.events.NavigateToUrlEvent', 'browser_use.browser.events', ('NavigateToUrlEvent',)
	),
	CompatibilityRequirement(
		'browser_use.browser.events.BrowserStateRequestEvent',
		'browser_use.browser.events',
		('BrowserStateRequestEvent',),
	),
	CompatibilityRequirement(
		'browser_use.browser.events.SwitchTabEvent', 'browser_use.browser.events', ('SwitchTabEvent',)
	),
	CompatibilityRequirement(
		'browser_use.browser.events.CloseTabEvent', 'browser_use.browser.events', ('CloseTabEvent',)
	),
	CompatibilityRequirement(
		'browser_use.mcp.server.BrowserUseServer', 'browser_use.mcp.server', ('BrowserUseServer',)
	),
)


def check_browser_use_compatibility(
	*,
	installed_version: str | None = None,
	requirements: Sequence[CompatibilityRequirement] = REQUIRED_INTERNALS,
) -> CompatibilityResult:
	detected_version = installed_version if installed_version is not None else _installed_browser_use_version()
	version_supported = detected_version == TARGET_BROWSER_USE_VERSION
	errors: list[str] = []
	if not version_supported:
		errors.append(f'unsupported browser-use version {detected_version or "not installed"}')

	checked_requirements = tuple(_check_requirement(requirement) for requirement in requirements)
	return CompatibilityResult(
		target_version=TARGET_BROWSER_USE_VERSION,
		installed_version=detected_version,
		version_supported=version_supported,
		requirements=checked_requirements,
		errors=tuple(errors),
	)


def _installed_browser_use_version() -> str | None:
	try:
		return version('browser-use')
	except PackageNotFoundError:
		return None


def _check_requirement(requirement: CompatibilityRequirement) -> CheckedRequirement:
	try:
		current: Any = import_module(requirement.module)
		for attribute in requirement.attribute_path:
			current = getattr(current, attribute)
	except Exception as exc:
		return CheckedRequirement(requirement.label, False, str(exc))

	return CheckedRequirement(requirement.label, True)
