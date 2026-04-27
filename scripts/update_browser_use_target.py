import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / 'src'
sys.path.insert(0, str(SRC_ROOT))

from browser_use_camoufox.compat.latest_pypi import build_latest_pypi_report  # noqa: E402


def main() -> int:
	parser = argparse.ArgumentParser()
	parser.add_argument('--check-only', action='store_true', help='report whether the target matches latest PyPI')
	args = parser.parse_args()

	if not args.check_only:
		parser.error('only --check-only is currently supported')

	report = build_latest_pypi_report()
	print(report.text)
	return 0 if report.ok else 1


if __name__ == '__main__':
	raise SystemExit(main())
