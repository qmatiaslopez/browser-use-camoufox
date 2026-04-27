from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_readme_documents_public_install_usage_and_boundaries():
	readme = (PROJECT_ROOT / 'README.md').read_text()

	assert 'uv add browser-use-camoufox' in readme
	assert 'from browser_use_camoufox import CamoufoxSession' in readme
	assert 'record_har_path' in readme
	assert 'record_video_dir' in readme
	assert 'No fake CDP' in readme
	assert 'uv run pytest -v tests/unit tests/integration tests/parity' in readme


def test_license_exists_with_mit_terms():
	license_text = (PROJECT_ROOT / 'LICENSE').read_text()

	assert 'MIT License' in license_text
	assert 'Permission is hereby granted' in license_text
