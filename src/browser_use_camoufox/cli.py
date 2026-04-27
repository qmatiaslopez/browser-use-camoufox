import argparse

from browser_use_camoufox import CamoufoxSession
from browser_use_camoufox.compat.latest_pypi import build_latest_pypi_report
from browser_use_camoufox.compat.surface_inventory import build_surface_inventory_report, format_surface_inventory_text
from browser_use_camoufox.conformance import run_conformance_sync
from browser_use_camoufox.diagnostics import build_doctor_report, check_dependencies


def main() -> int:
	parser = argparse.ArgumentParser(prog='browser-use-camoufox')
	subparsers = parser.add_subparsers(dest='command')
	doctor_parser = subparsers.add_parser('doctor')
	doctor_parser.add_argument('--runtime-smoke', action='store_true')
	conformance_parser = subparsers.add_parser('conformance')
	conformance_parser.add_argument('--matrix', choices=['current'], default='current')
	conformance_parser.add_argument('--fixtures-only', action='store_true')
	conformance_parser.add_argument('--include-public', action='store_true')
	compatibility_parser = subparsers.add_parser('compatibility')
	compatibility_parser.add_argument('--latest-pypi', action='store_true')
	compatibility_parser.add_argument('--surface-inventory', action='store_true')
	args = parser.parse_args()

	if args.command == 'doctor':
		report = build_doctor_report(check_dependencies())
		print(report.text)
		if not report.ok:
			return 1
		if args.runtime_smoke:
			import asyncio

			asyncio.run(_run_runtime_smoke())
			print('runtime smoke: ok')
		return 0

	if args.command == 'conformance':
		report = run_conformance_sync(
			matrix_name=args.matrix,
			fixtures_only=args.fixtures_only,
			include_public=args.include_public,
		)
		print(report.to_json())
		return 0 if report.ok else 1

	if args.command == 'compatibility':
		if args.latest_pypi:
			report = build_latest_pypi_report()
			print(report.text)
			return 0 if report.ok else 1
		if args.surface_inventory:
			print(format_surface_inventory_text(build_surface_inventory_report()))
			return 0
		compatibility_parser.print_help()
		return 2

	parser.print_help()
	return 2


async def _run_runtime_smoke() -> None:
	session = CamoufoxSession(headless=True)
	try:
		await session.start()
		await session.navigate_to('about:blank')
		await session.take_screenshot()
	finally:
		await session.stop()
