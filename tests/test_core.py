import json
import pytest

from eval_gate.core import InputError, compare, load, render_markdown
from eval_gate.cli import main


def mk(rows):
    return load(json.dumps(r) for r in rows)


def runs(case, results, tags=()):
    return [{"case": case, "run": i, "passed": p, "tags": list(tags)} for i, p in enumerate(results, 1)]


def kinds(findings):
    return {(f.kind, f.case) for f in findings}


def test_identical_runs_pass():
    d = mk(runs("a", [True] * 3))
    f, s = compare(d, d)
    assert f == [] and s["errors"] == 0


def test_regression_is_error():
    f, s = compare(mk(runs("a", [True] * 4)), mk(runs("a", [True, True, False, False])))
    assert ("regression", "a") in kinds(f) and s["errors"] >= 1


def test_critical_case_has_zero_tolerance():
    base = mk(runs("a", [True] * 10, ["critical"]))
    cand = mk(runs("a", [True] * 9 + [False], ["critical"]))
    f, _ = compare(base, cand, max_drop=0.5)
    assert ("regression", "a") in kinds(f)


def test_non_critical_respects_max_drop():
    base = mk(runs("a", [True] * 10))
    cand = mk(runs("a", [True] * 9 + [False]))
    f, _ = compare(base, cand, max_drop=0.2, max_overall_drop=0.5)
    assert ("regression", "a") not in kinds(f)


def test_lost_case_is_error_when_critical_and_warn_otherwise():
    base = mk(runs("a", [True], ["critical"]) + runs("b", [True]))
    cand = mk(runs("c", [True]))
    f, _ = compare(base, cand, max_overall_drop=1)
    sev = {x.case: x.severity for x in f if x.kind == "lost"}
    assert sev == {"a": "error", "b": "warn"}
    assert ("new-case", "c") in kinds(f)


def test_new_flakiness_is_warning_only():
    f, s = compare(mk(runs("a", [True] * 4)), mk(runs("a", [True] * 4)))
    assert s["warnings"] == 0
    base = mk(runs("a", [True, False]))
    cand = mk(runs("a", [True, False]))
    f, _ = compare(base, cand)
    assert not any(x.kind == "flaky-new" for x in f)  # was already flaky


def test_flaky_new_detected_when_rate_equal():
    base = mk(runs("a", [True, True, False, False]))
    cand = mk(runs("a", [True, False, True, False]))
    # both flaky -> no flaky-new
    f, _ = compare(base, cand)
    assert not any(x.kind == "flaky-new" for x in f)
    base = mk(runs("a", [False, False]))
    cand = mk(runs("a", [True, False]))
    f, _ = compare(base, cand)
    assert ("fixed", "a") in kinds(f) and ("flaky-new", "a") in kinds(f)


def test_overall_drop_gate():
    base = mk(sum((runs(f"c{i}", [True] * 10) for i in range(5)), []))
    cand_rows = sum((runs(f"c{i}", [True] * 9 + [False]) for i in range(5)), [])
    f, s = compare(base, mk(cand_rows), max_drop=0.2, max_overall_drop=0.02)
    assert ("regression", "(overall)") in kinds(f) and s["errors"] == 1


def test_bad_input_rejected():
    with pytest.raises(InputError):
        load(["not json"])
    with pytest.raises(InputError):
        load(['{"case": "a"}'])
    with pytest.raises(InputError):
        load([""])


def test_markdown_has_verdict():
    f, s = compare(mk(runs("a", [True])), mk(runs("a", [False])))
    assert render_markdown(f, s).strip().endswith("Result: FAIL")


def test_cli_exit_codes(tmp_path, capsys):
    b = tmp_path / "b.jsonl"
    c = tmp_path / "c.jsonl"
    b.write_text("\n".join(json.dumps(r) for r in runs("a", [True, True])))
    c.write_text("\n".join(json.dumps(r) for r in runs("a", [True, True])))
    assert main([str(b), str(c)]) == 0
    c.write_text("\n".join(json.dumps(r) for r in runs("a", [False, False])))
    assert main([str(b), str(c)]) == 1
    assert main([str(b), str(tmp_path / "missing.jsonl")]) == 2


def test_bundled_example_fails_as_documented(capsys):
    assert main(["examples/baseline.jsonl", "examples/candidate.jsonl"]) == 1
    out = capsys.readouterr().out
    assert "escalate-to-human" in out and "missing from the candidate" in out
    assert "tool-timeout-retry" in out
