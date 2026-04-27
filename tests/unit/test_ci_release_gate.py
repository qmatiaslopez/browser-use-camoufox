from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_ci_workflow_runs_release_validation_gate():
	workflow = (PROJECT_ROOT / '.github' / 'workflows' / 'ci.yml').read_text()

	assert 'python-version: ["3.11", "3.12"]' in workflow
	assert 'uv run camoufox fetch' in workflow
	assert 'uv run pytest -v tests/unit tests/integration tests/parity' in workflow
	assert 'uv run browser-use-camoufox doctor' in workflow
	assert 'uv run browser-use-camoufox doctor --runtime-smoke' in workflow
	assert 'uv run browser-use-camoufox compatibility --surface-inventory' in workflow
	assert 'uv run browser-use-camoufox conformance --matrix current --fixtures-only' in workflow
	assert 'uv run ruff check src tests scripts' in workflow
	assert 'uv run ruff format --check src tests scripts' in workflow
	assert 'uv run pyright' in workflow
	assert 'uv run python -m pip check' in workflow
	assert 'uv build' in workflow
	assert 'python -m venv /tmp/browser-use-camoufox-verify' in workflow
	assert '/tmp/browser-use-camoufox-verify/bin/browser-use-camoufox doctor' in workflow
	assert '/tmp/browser-use-camoufox-verify/bin/python -m pip check' in workflow
	assert 'from browser_use_camoufox import CamoufoxSession' in workflow


def test_ci_workflow_has_scheduled_latest_pypi_check():
	workflow = (PROJECT_ROOT / '.github' / 'workflows' / 'ci.yml').read_text()

	assert 'schedule:' in workflow
	assert 'uv run browser-use-camoufox compatibility --latest-pypi' in workflow
