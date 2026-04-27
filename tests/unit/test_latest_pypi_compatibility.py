import json
from urllib.error import URLError

from browser_use_camoufox.compat.latest_pypi import (
	LatestCompatibilityReport,
	build_latest_pypi_report,
	fetch_latest_browser_use_version,
)


class FakeResponse:
	def __init__(self, payload: dict[str, object]):
		self._payload = payload

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc, traceback):
		return False

	def read(self) -> bytes:
		return json.dumps(self._payload).encode()


def test_fetch_latest_browser_use_version_from_pypi_json():
	def opener(url: str, timeout: float):
		assert url == 'https://pypi.org/pypi/browser-use/json'
		assert timeout == 10
		return FakeResponse({'info': {'version': '0.13.0'}})

	assert fetch_latest_browser_use_version(opener=opener) == '0.13.0'


def test_fetch_latest_browser_use_version_reports_bad_payload():
	def opener(url: str, timeout: float):
		return FakeResponse({'info': {}})

	try:
		fetch_latest_browser_use_version(opener=opener)
	except RuntimeError as exc:
		assert 'missing latest browser-use version' in str(exc)
	else:
		raise AssertionError('expected RuntimeError')


def test_latest_report_is_supported_when_pypi_matches_target():
	report = build_latest_pypi_report(latest_version_fetcher=lambda: '0.12.6')

	assert report.ok is True
	assert report.latest_version == '0.12.6'
	assert report.action_required is False
	assert 'status: supported' in report.text


def test_latest_report_is_actionable_when_pypi_differs_from_target():
	report = build_latest_pypi_report(latest_version_fetcher=lambda: '0.13.0')

	assert report.ok is False
	assert report.latest_version == '0.13.0'
	assert report.action_required is True
	assert 'status: unsupported latest PyPI browser-use' in report.text
	assert 'action: review Browser-Use 0.13.0 internals' in report.text


def test_latest_report_handles_pypi_lookup_failure():
	report = build_latest_pypi_report(latest_version_fetcher=lambda: (_ for _ in ()).throw(URLError('offline')))

	assert report.ok is False
	assert report.latest_version is None
	assert report.error == '<urlopen error offline>'
	assert 'error: failed to fetch latest PyPI browser-use version' in report.text


def test_report_json_is_stable_for_cli_output():
	report = LatestCompatibilityReport(
		ok=False,
		target_version='0.12.6',
		latest_version='0.13.0',
		action_required=True,
		error=None,
	)

	assert json.loads(report.to_json()) == {
		'ok': False,
		'target_version': '0.12.6',
		'latest_version': '0.13.0',
		'action_required': True,
		'error': None,
	}
