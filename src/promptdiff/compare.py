"""Comparing suite runs across two prompt versions.

The core idea: run the same fixed suite through two runners (typically two
ReplayRunners pointed at different fixture versions) and report which
*assertions* flipped, not just whether the raw text differs. A prompt can
change its wording completely and still pass every assertion -- that is
not a regression. A one-character change that breaks JSON parsing on one
case *is* a regression, even though the text diff looks tiny.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass

from promptdiff.evaluate import CaseResult, pass_rate, run_suite
from promptdiff.runner import Runner
from promptdiff.suite import Suite

TransitionKind = str  # one of: "regression", "improvement", "unchanged_pass", "unchanged_fail"

REGRESSION = "regression"
IMPROVEMENT = "improvement"
UNCHANGED_PASS = "unchanged_pass"
UNCHANGED_FAIL = "unchanged_fail"


@dataclass(frozen=True)
class AssertionTransition:
    """How a single assertion's verdict changed between base and head."""

    assertion_type: str
    description: str
    base_passed: bool
    head_passed: bool
    base_message: str
    head_message: str

    @property
    def kind(self) -> TransitionKind:
        if self.base_passed and not self.head_passed:
            return REGRESSION
        if not self.base_passed and self.head_passed:
            return IMPROVEMENT
        if self.base_passed and self.head_passed:
            return UNCHANGED_PASS
        return UNCHANGED_FAIL


@dataclass(frozen=True)
class CaseComparison:
    """The comparison of one case's base and head runs."""

    case_id: str
    base_output: str
    head_output: str
    transitions: tuple[AssertionTransition, ...]

    @property
    def base_passed(self) -> bool:
        return all(t.base_passed for t in self.transitions)

    @property
    def head_passed(self) -> bool:
        return all(t.head_passed for t in self.transitions)

    @property
    def verdict_changed(self) -> bool:
        return self.base_passed != self.head_passed

    @property
    def text_changed(self) -> bool:
        return self.base_output != self.head_output

    @property
    def has_regression(self) -> bool:
        return any(t.kind == REGRESSION for t in self.transitions)

    @property
    def has_improvement(self) -> bool:
        return any(t.kind == IMPROVEMENT for t in self.transitions)

    def text_diff(self) -> str:
        """A unified text diff between the base and head outputs.

        This is provided for human inspection only -- promptdiff never
        uses it to decide pass/fail. Line-oriented; each output is split
        into lines for the diff.
        """
        diff = difflib.unified_diff(
            self.base_output.splitlines(keepends=True),
            self.head_output.splitlines(keepends=True),
            fromfile="base",
            tofile="head",
        )
        return "".join(diff)


@dataclass(frozen=True)
class CompareReport:
    """The full comparison of a suite run across two versions."""

    suite_name: str | None
    base_version: str
    head_version: str
    cases: tuple[CaseComparison, ...]

    @property
    def base_pass_rate(self) -> float:
        if not self.cases:
            return 1.0
        return sum(1 for c in self.cases if c.base_passed) / len(self.cases)

    @property
    def head_pass_rate(self) -> float:
        if not self.cases:
            return 1.0
        return sum(1 for c in self.cases if c.head_passed) / len(self.cases)

    @property
    def pass_rate_delta(self) -> float:
        return self.head_pass_rate - self.base_pass_rate

    @property
    def regressions(self) -> tuple[CaseComparison, ...]:
        return tuple(c for c in self.cases if c.has_regression)

    @property
    def improvements(self) -> tuple[CaseComparison, ...]:
        return tuple(c for c in self.cases if c.has_improvement)

    @property
    def has_regressions(self) -> bool:
        return bool(self.regressions)


def _pair_results(
    base_results: tuple[CaseResult, ...], head_results: tuple[CaseResult, ...]
) -> tuple[CaseComparison, ...]:
    head_by_id = {r.case_id: r for r in head_results}
    comparisons = []
    for base_result in base_results:
        head_result = head_by_id.get(base_result.case_id)
        if head_result is None:
            raise ValueError(
                f"case {base_result.case_id!r} present in base run but missing from head run"
            )
        if len(base_result.assertion_results) != len(head_result.assertion_results):
            raise ValueError(
                f"case {base_result.case_id!r} has a different number of assertion results "
                f"between base ({len(base_result.assertion_results)}) and head "
                f"({len(head_result.assertion_results)}) -- the suite must be identical for "
                "both versions"
            )
        transitions = tuple(
            AssertionTransition(
                assertion_type=base_ar.assertion_type,
                description=base_ar.description,
                base_passed=base_ar.passed,
                head_passed=head_ar.passed,
                base_message=base_ar.message,
                head_message=head_ar.message,
            )
            for base_ar, head_ar in zip(
                base_result.assertion_results, head_result.assertion_results, strict=True
            )
        )
        comparisons.append(
            CaseComparison(
                case_id=base_result.case_id,
                base_output=base_result.output,
                head_output=head_result.output,
                transitions=transitions,
            )
        )
    return tuple(comparisons)


def compare_versions(
    suite: Suite,
    base_runner: Runner,
    head_runner: Runner,
    *,
    base_version: str,
    head_version: str,
) -> CompareReport:
    """Run a suite through two runners and produce a behavioural comparison."""
    base_results = run_suite(suite, base_runner)
    head_results = run_suite(suite, head_runner)
    comparisons = _pair_results(base_results, head_results)
    return CompareReport(
        suite_name=suite.name,
        base_version=base_version,
        head_version=head_version,
        cases=comparisons,
    )


__all__ = [
    "AssertionTransition",
    "CaseComparison",
    "CompareReport",
    "compare_versions",
    "REGRESSION",
    "IMPROVEMENT",
    "UNCHANGED_PASS",
    "UNCHANGED_FAIL",
    "pass_rate",
]
