import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Protocol
from urllib.request import urlopen

from browser_use_camoufox.diagnostics import TARGET_BROWSER_USE_VERSION

PYPI_BROWSER_USE_JSON_URL = 'https://pypi.org/pypi/browser-use/json'


class UrlResponse(Protocol):
	def __enter__(self) -> 'UrlResponse': ...

	def __exit__(self, exc_type: object, exc: object, traceback: object) -> object: ...

	def read(self) -> bytes: ...


def _open_url(url: str, timeout: float) -> UrlResponse:
	return urlopen(url, timeout=timeout)


@dataclass(frozen=True)
class LatestCompatibilityReport:
	ok: bool
	target_version: str
	latest_version: str | None
	action_required: bool
	error: str | None

	@property
	def text(self) -> str:
		lines = [
			'browser-use-camoufox latest PyPI compatibility',
			f'target browser-use: {self.target_version}',
			f'latest PyPI browser-use: {self.latest_version or "unknown"}',
		]
		if self.error:
			lines.append(f'error: failed to fetch latest PyPI browser-use version: {self.error}')
		elif self.ok:
			lines.append('status: supported')
		else:
			lines.append('status: unsupported latest PyPI browser-use')
			lines.append(f'action: review Browser-Use {self.latest_version} internals and update compatibility target')
		return '\n'.join(lines)

	def to_json(self) -> str:
		return json.dumps(asdict(self), sort_keys=True)


def fetch_latest_browser_use_version(
	*,
	opener: Callable[[str, float], UrlResponse] = _open_url,
	timeout: float = 10,
) -> str:
	with opener(PYPI_BROWSER_USE_JSON_URL, timeout) as response:
		payload = json.loads(response.read().decode())

	latest_version = payload.get('info', {}).get('version')
	if not isinstance(latest_version, str) or not latest_version:
		raise RuntimeError('missing latest browser-use version in PyPI response')
	return latest_version


def build_latest_pypi_report(
	*,
	latest_version_fetcher: Callable[[], str] = fetch_latest_browser_use_version,
) -> LatestCompatibilityReport:
	try:
		latest_version = latest_version_fetcher()
	except Exception as exc:
		return LatestCompatibilityReport(
			ok=False,
			target_version=TARGET_BROWSER_USE_VERSION,
			latest_version=None,
			action_required=True,
			error=str(exc),
		)

	ok = latest_version == TARGET_BROWSER_USE_VERSION
	return LatestCompatibilityReport(
		ok=ok,
		target_version=TARGET_BROWSER_USE_VERSION,
		latest_version=latest_version,
		action_required=not ok,
		error=None,
	)
