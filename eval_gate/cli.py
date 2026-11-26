import argparse
import sys

from .core import InputError, compare, load, render_markdown


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="eval-gate", description="Compare two eval runs (JSONL) and gate CI.")
    p.add_argument("baseline")
    p.add_argument("candidate")
    p.add_argument("--max-drop", type=float, default=0.0, help="allowed per-case pass-rate drop (0-1), non-critical cases")
    p.add_argument("--max-overall-drop", type=float, default=0.02)
    p.add_argument("--critical-tag", default="critical")
    p.add_argument("--out", help="write the markdown report to this file")
    a = p.parse_args(argv)
    try:
        with open(a.baseline, encoding="utf-8") as f:
            base = load(f)
        with open(a.candidate, encoding="utf-8") as f:
            cand = load(f)
    except (OSError, InputError) as e:
        print(f"eval-gate: {e}", file=sys.stderr)
        return 2
    findings, summary = compare(base, cand, max_drop=a.max_drop,
                                critical_tag=a.critical_tag, max_overall_drop=a.max_overall_drop)
    md = render_markdown(findings, summary)
    print(md, end="")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(md)
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
