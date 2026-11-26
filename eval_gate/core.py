"""Core logic. Pure functions, no network, no dependencies.

Input format (JSONL, one result per line):
    {"case": "refund-flow", "run": 1, "passed": true, "tags": ["critical"]}
`run` is optional. Several lines with the same `case` are repeated runs.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field


class InputError(ValueError):
    pass


@dataclass
class CaseStats:
    case: str
    passes: int = 0
    runs: int = 0
    tags: set = field(default_factory=set)

    @property
    def rate(self) -> float:
        return self.passes / self.runs if self.runs else 0.0

    @property
    def flaky(self) -> bool:
        return 0 < self.passes < self.runs


def load(lines) -> dict[str, CaseStats]:
    out: dict[str, CaseStats] = {}
    for n, raw in enumerate(lines, 1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as e:
            raise InputError(f"line {n}: not valid JSON ({e.msg})") from None
        if not isinstance(row, dict) or "case" not in row or not isinstance(row.get("passed"), bool):
            raise InputError(f'line {n}: needs "case" and boolean "passed"')
        s = out.setdefault(str(row["case"]), CaseStats(str(row["case"])))
        s.runs += 1
        s.passes += 1 if row["passed"] else 0
        s.tags.update(row.get("tags") or [])
    if not out:
        raise InputError("no results found")
    return out


@dataclass
class Finding:
    kind: str       # regression | lost | flaky-new | fixed | new-case
    severity: str   # error | warn | info
    case: str
    detail: str


def compare(base, cand, *, max_drop=0.0, critical_tag="critical", max_overall_drop=0.02):
    """Return (findings, summary). A case regresses when its pass rate falls
    by more than `max_drop`. Critical cases use max_drop=0 always."""
    findings: list[Finding] = []
    for name, b in sorted(base.items()):
        c = cand.get(name)
        crit = critical_tag in b.tags
        if c is None:
            findings.append(Finding("lost", "error" if crit else "warn", name,
                                    "case is in the baseline but missing from the candidate run"))
            continue
        drop = b.rate - c.rate
        limit = 0.0 if crit else max_drop
        if drop > limit + 1e-9:
            findings.append(Finding("regression", "error", name,
                                    f"pass rate {b.rate:.0%} -> {c.rate:.0%}" + (" (critical)" if crit else "")))
        elif c.rate - b.rate > 1e-9:
            findings.append(Finding("fixed", "info", name, f"pass rate {b.rate:.0%} -> {c.rate:.0%}"))
        if c.flaky and not b.flaky and c.rate >= b.rate - 1e-9 and drop <= limit + 1e-9:
            findings.append(Finding("flaky-new", "warn", name,
                                    f"mixed results over {c.runs} runs ({c.passes} passed); baseline was stable"))
    for name in sorted(set(cand) - set(base)):
        findings.append(Finding("new-case", "info", name, "case is new, no baseline to compare"))

    def overall(d):
        runs = sum(s.runs for s in d.values())
        return sum(s.passes for s in d.values()) / runs if runs else 0.0

    bo, co = overall(base), overall(cand)
    if bo - co > max_overall_drop + 1e-9:
        findings.append(Finding("regression", "error", "(overall)",
                                f"overall pass rate {bo:.1%} -> {co:.1%}, limit is {max_overall_drop:.1%}"))
    summary = {"baseline_rate": bo, "candidate_rate": co,
               "errors": sum(f.severity == "error" for f in findings),
               "warnings": sum(f.severity == "warn" for f in findings)}
    return findings, summary


def render_markdown(findings, summary) -> str:
    lines = ["# eval-gate report", "",
             f"Overall pass rate: {summary['baseline_rate']:.1%} -> {summary['candidate_rate']:.1%}",
             f"Errors: {summary['errors']}, warnings: {summary['warnings']}", ""]
    if not findings:
        lines.append("No differences found.")
    else:
        lines += ["| Severity | Kind | Case | Detail |", "|---|---|---|---|"]
        order = {"error": 0, "warn": 1, "info": 2}
        for f in sorted(findings, key=lambda f: (order[f.severity], f.case)):
            lines.append(f"| {f.severity} | {f.kind} | {f.case} | {f.detail} |")
    lines.append("")
    lines.append("Result: " + ("FAIL" if summary["errors"] else "PASS"))
    return "\n".join(lines) + "\n"
