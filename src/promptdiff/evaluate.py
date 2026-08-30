"""Running a suite against a single runner and collecting results."""

from __future__ import annotations

from dataclasses import dataclass

from promptdiff.assertions import AssertionResult
from promptdiff.runner import Runner
from promptdiff.suite import Suite


@dataclass(frozen=True)
class CaseResult:
    """The outcome of running one case: its output and every assertion result."""

    case_id: str
    output: str
    assertion_results: tuple[AssertionResult, ...]

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.assertion_results)

    @property
    def failed_assertions(self) -> tuple[AssertionResult, ...]:
        return tuple(r for r in self.assertion_results if not r.passed)


def run_suite(suite: Suite, runner: Runner) -> tuple[CaseResult, ...]:
    """Run every case in a suite through a runner and check its assertions."""
    results = []
    for case in suite.cases:
        output = runner.run(case.id, case.input)
        assertion_results = tuple(a.check(output) for a in case.assertions)
        results.append(
            CaseResult(case_id=case.id, output=output, assertion_results=assertion_results)
        )
    return tuple(results)


def pass_rate(results: tuple[CaseResult, ...]) -> float:
    """The fraction of cases that passed all their assertions, in [0.0, 1.0].

    Returns 1.0 for an empty result set (vacuously, nothing failed).
    """
    if not results:
        return 1.0
    return sum(1 for r in results if r.passed) / len(results)
