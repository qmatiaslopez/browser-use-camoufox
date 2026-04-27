from dataclasses import dataclass
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version

TARGET_BROWSER_USE_VERSION = '0.12.6'


@dataclass(frozen=True)
class DependencyStatus:
	@dataclass(frozen=True)
	class PackageStatus:
		name: str
		installed: bool
		version: str | None
		error: str | None

	browser_use: PackageStatus
	camoufox: PackageStatus


@dataclass(frozen=True)
class DoctorReport:
	ok: bool
	text: str


def _check_package(distribution_name: str, import_name: str) -> DependencyStatus.PackageStatus:
	try:
		import_module(import_name)
	except Exception as exc:
		return DependencyStatus.PackageStatus(distribution_name, False, None, str(exc))

	try:
		package_version = version(distribution_name)
	except PackageNotFoundError:
		package_version = None

	return DependencyStatus.PackageStatus(distribution_name, True, package_version, None)


def check_dependencies() -> DependencyStatus:
	return DependencyStatus(
		browser_use=_check_package('browser-use', 'browser_use'),
		camoufox=_check_package('camoufox', 'camoufox'),
	)


def build_doctor_report(status: DependencyStatus) -> DoctorReport:
	from browser_use_camoufox.compat.detector import check_browser_use_compatibility

	compatibility = check_browser_use_compatibility(installed_version=status.browser_use.version)
	lines = [
		'browser-use-camoufox doctor',
		_package_line(status.browser_use),
		_package_line(status.camoufox),
		f'target browser-use: {TARGET_BROWSER_USE_VERSION}',
	]

	if compatibility.ok:
		lines.append('compatibility: supported')
	else:
		lines.append('compatibility: unsupported')
		for error in compatibility.errors:
			lines.append(f'error: {error}')
		for missing_requirement in compatibility.missing_requirements:
			lines.append(f'error: missing Browser-Use internal {missing_requirement}')

	if not status.browser_use.installed:
		lines.append('remediation: uv add browser-use==0.12.6')
	if not status.camoufox.installed:
		lines.append('remediation: uv add cloverlabs-camoufox && uv run camoufox fetch')
	else:
		lines.append('asset check: run `uv run camoufox fetch` if Camoufox browser assets are missing')

	ok = status.browser_use.installed and status.camoufox.installed and compatibility.ok
	return DoctorReport(ok, '\n'.join(lines))


def _package_line(package: DependencyStatus.PackageStatus) -> str:
	if package.installed:
		version_text = package.version or 'unknown version'
		return f'{package.name}: installed ({version_text})'
	return f'{package.name}: missing ({package.error})'
