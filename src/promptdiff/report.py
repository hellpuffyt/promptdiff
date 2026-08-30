"""Rendering run and compare results as a human table or JSON."""

from __future__ import annotations

import json
from typing import Any

from promptdiff.compare import CompareReport
from promptdiff.evaluate import CaseResult, pass_rate


def _wrap(text: str, width: int) -> str:
    text = text.replace("\n", "\\n")
    if len(text) <= width:
        return text
    return text[: width - 1] + "…"


def _table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    lines = []
    header_line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    lines.append(header_line)
    lines.append("  ".join("-" * w for w in widths))
    for row in rows:
        lines.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
    return "\n".join(lines)


def render_run_table(results: tuple[CaseResult, ...]) -> str:
    rows = []
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        failed = ", ".join(a.assertion_type for a in result.failed_assertions)
        rows.append([result.case_id, status, _wrap(failed, 40)])
    table = _table(["case", "status", "failed_assertions"], rows)
    rate = pass_rate(results)
    summary = f"\n{sum(1 for r in results if r.passed)}/{len(results)} cases passed ({rate:.0%})"
    return table + summary


def render_run_json(results: tuple[CaseResult, ...]) -> str:
    payload: dict[str, Any] = {
        "cases": [
            {
                "case_id": r.case_id,
                "passed": r.passed,
                "output": r.output,
                "assertions": [
                    {
                        "type": a.assertion_type,
                        "description": a.description,
                        "passed": a.passed,
                        "message": a.message,
                    }
                    for a in r.assertion_results
                ],
            }
            for r in results
        ],
        "pass_rate": pass_rate(results),
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
    }
    return json.dumps(payload, indent=2)


def render_compare_table(report: CompareReport, *, show_text_diff: bool = False) -> str:
    rows = []
    for case in report.cases:
        base_status = "PASS" if case.base_passed else "FAIL"
        head_status = "PASS" if case.head_passed else "FAIL"
        verdict = "CHANGED" if case.verdict_changed else "same"
        regressed = ", ".join(
            t.assertion_type for t in case.transitions if t.kind == "regression"
        )
        improved = ", ".join(
            t.assertion_type for t in case.transitions if t.kind == "improvement"
        )
        flags = []
        if regressed:
            flags.append(f"regressed: {regressed}")
        if improved:
            flags.append(f"improved: {improved}")
        rows.append(
            [
                case.case_id,
                f"{base_status} -> {head_status}",
                verdict,
                _wrap("; ".join(flags), 50),
            ]
        )
    table = _table(["case", "base -> head", "verdict", "assertion transitions"], rows)

    lines = [table, ""]
    lines.append(f"suite: {report.suite_name or '(unnamed)'}")
    lines.append(f"base={report.base_version}  head={report.head_version}")
    lines.append(
        f"pass rate: {report.base_pass_rate:.0%} -> {report.head_pass_rate:.0%} "
        f"({report.pass_rate_delta:+.0%})"
    )
    lines.append(
        f"regressions: {len(report.regressions)}   improvements: {len(report.improvements)}"
    )

    if show_text_diff:
        changed = [c for c in report.cases if c.text_changed]
        if changed:
            lines.append("")
            lines.append("text diffs:")
            for case in changed:
                lines.append(f"--- {case.case_id} ---")
                lines.append(case.text_diff().rstrip("\n"))

    return "\n".join(lines)


def render_compare_json(report: CompareReport, *, show_text_diff: bool = False) -> str:
    payload: dict[str, Any] = {
        "suite_name": report.suite_name,
        "base_version": report.base_version,
        "head_version": report.head_version,
        "base_pass_rate": report.base_pass_rate,
        "head_pass_rate": report.head_pass_rate,
        "pass_rate_delta": report.pass_rate_delta,
        "regression_count": len(report.regressions),
        "improvement_count": len(report.improvements),
        "cases": [
            {
                "case_id": case.case_id,
                "base_passed": case.base_passed,
                "head_passed": case.head_passed,
                "verdict_changed": case.verdict_changed,
                "text_changed": case.text_changed,
                "has_regression": case.has_regression,
                "has_improvement": case.has_improvement,
                "transitions": [
                    {
                        "assertion_type": t.assertion_type,
                        "description": t.description,
                        "base_passed": t.base_passed,
                        "head_passed": t.head_passed,
                        "kind": t.kind,
                        "base_message": t.base_message,
                        "head_message": t.head_message,
                    }
                    for t in case.transitions
                ],
                **(
                    {"text_diff": case.text_diff()}
                    if show_text_diff and case.text_changed
                    else {}
                ),
            }
            for case in report.cases
        ],
    }
    return json.dumps(payload, indent=2)
