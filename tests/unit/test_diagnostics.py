from browser_use_camoufox.diagnostics import DependencyStatus, build_doctor_report, check_dependencies


def test_check_dependencies_reports_browser_use_and_camoufox():
	status = check_dependencies()

	assert status.browser_use.installed is True
	assert status.browser_use.version
	assert status.camoufox.installed is True


def test_doctor_report_is_successful_when_dependencies_are_available():
	status = DependencyStatus(
		browser_use=DependencyStatus.PackageStatus('browser-use', True, '0.12.6', None),
		camoufox=DependencyStatus.PackageStatus('camoufox', True, '0.5.0', None),
	)

	report = build_doctor_report(status)

	assert report.ok is True
	assert 'browser-use: installed (0.12.6)' in report.text
	assert 'camoufox: installed (0.5.0)' in report.text


def test_doctor_report_fails_with_actionable_missing_dependency():
	status = DependencyStatus(
		browser_use=DependencyStatus.PackageStatus('browser-use', False, None, 'No module named browser_use'),
		camoufox=DependencyStatus.PackageStatus('camoufox', False, None, 'No module named camoufox'),
	)

	report = build_doctor_report(status)

	assert report.ok is False
	assert 'uv add browser-use==0.12.6' in report.text
	assert 'uv run camoufox fetch' in report.text
