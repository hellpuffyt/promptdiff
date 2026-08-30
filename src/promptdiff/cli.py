"""The promptdiff command-line interface.

Two subcommands:

  promptdiff run      -- run a suite against one prompt version, report pass/fail.
  promptdiff compare   -- run a suite against two prompt versions, report the
                           behavioural diff between them.

Both subcommands use a ReplayRunner, reading recorded outputs from a
fixtures directory -- see README.md for how to plug in a live provider
instead by writing your own Runner and calling the library functions
directly.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from promptdiff.assertions import AssertionSpecError
from promptdiff.compare import compare_versions
from promptdiff.evaluate import run_suite
from promptdiff.report import (
    render_compare_json,
    render_compare_table,
    render_run_json,
    render_run_table,
)
from promptdiff.runner import FixtureNotFoundError, ReplayRunner
from promptdiff.suite import SuiteParseError, load_suite

EXIT_OK = 0
EXIT_FAILURES_OR_REGRESSIONS = 1
EXIT_USAGE_ERROR = 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="promptdiff",
        description="A regression harness for prompt changes.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run", help="run a suite against one prompt version"
    )
    run_parser.add_argument("--suite", required=True, type=Path, help="path to the suite file")
    run_parser.add_argument(
        "--fixtures", required=True, type=Path, help="path to the fixtures directory"
    )
    run_parser.add_argument(
        "--version", required=True, help="fixture subdirectory name to replay"
    )
    run_parser.add_argument(
        "--format", choices=["table", "json"], default="table", help="output format"
    )

    compare_parser = subparsers.add_parser(
        "compare", help="compare a suite's behaviour across two prompt versions"
    )
    compare_parser.add_argument("--suite", required=True, type=Path, help="path to the suite file")
    compare_parser.add_argument(
        "--fixtures", required=True, type=Path, help="path to the fixtures directory"
    )
    compare_parser.add_argument("--base", required=True, help="base fixture subdirectory name")
    compare_parser.add_argument("--head", required=True, help="head fixture subdirectory name")
    compare_parser.add_argument(
        "--format", choices=["table", "json"], default="table", help="output format"
    )
    compare_parser.add_argument(
        "--text-diff",
        action="store_true",
        help="include a unified text diff of changed outputs (for inspection only; "
        "never used to decide pass/fail)",
    )
    compare_parser.add_argument(
        "--allow-regression",
        action="store_true",
        help="exit 0 even if the comparison found regressions",
    )

    return parser


def _cmd_run(args: argparse.Namespace) -> int:
    suite = load_suite(args.suite)
    runner = ReplayRunner(args.fixtures, args.version)
    results = run_suite(suite, runner)

    if args.format == "json":
        print(render_run_json(results))
    else:
        print(render_run_table(results))

    if all(r.passed for r in results):
        return EXIT_OK
    return EXIT_FAILURES_OR_REGRESSIONS


def _cmd_compare(args: argparse.Namespace) -> int:
    suite = load_suite(args.suite)
    base_runner = ReplayRunner(args.fixtures, args.base)
    head_runner = ReplayRunner(args.fixtures, args.head)
    report = compare_versions(
        suite,
        base_runner,
        head_runner,
        base_version=args.base,
        head_version=args.head,
    )

    if args.format == "json":
        print(render_compare_json(report, show_text_diff=args.text_diff))
    else:
        print(render_compare_table(report, show_text_diff=args.text_diff))

    if not report.has_regressions or args.allow_regression:
        return EXIT_OK
    return EXIT_FAILURES_OR_REGRESSIONS


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "run":
            return _cmd_run(args)
        if args.command == "compare":
            return _cmd_compare(args)
        parser.error(f"unknown command: {args.command}")
        return EXIT_USAGE_ERROR  # pragma: no cover - argparse.error exits
    except (SuiteParseError, AssertionSpecError, FixtureNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR


if __name__ == "__main__":
    sys.exit(main())
