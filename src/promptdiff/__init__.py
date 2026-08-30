"""promptdiff: a regression harness for prompt changes.

Run a fixed evaluation suite across prompt versions and report behavioural
deltas -- which cases changed verdict, which assertions newly fail, and the
aggregate pass-rate delta -- rather than just a text diff of raw outputs.
"""

from promptdiff.assertions import (
    Assertion,
    AssertionResult,
    parse_assertion,
)
from promptdiff.compare import CaseComparison, CompareReport, compare_versions
from promptdiff.evaluate import CaseResult, pass_rate, run_suite
from promptdiff.runner import FixtureNotFoundError, ReplayRunner, Runner
from promptdiff.suite import Case, Suite, SuiteParseError, load_suite

__version__ = "0.1.0"

__all__ = [
    "Assertion",
    "AssertionResult",
    "parse_assertion",
    "CaseComparison",
    "CompareReport",
    "compare_versions",
    "CaseResult",
    "pass_rate",
    "run_suite",
    "FixtureNotFoundError",
    "ReplayRunner",
    "Runner",
    "Case",
    "Suite",
    "SuiteParseError",
    "load_suite",
    "__version__",
]
