# eval-gate

A small CI gate for LLM agent evals. You give it two result files, one from the baseline and one from the new version, and it fails the build when the new version is worse.

Independent demo, not affiliated with Fusemachines. I wrote it after applying for a Machine Learning Engineer role that asks for evals gated in CI. All data in `examples/` is invented.

## What it checks

- **Regression.** A case passes less often than before. Cases tagged `critical` allow no drop at all. Other cases allow `--max-drop` (default 0).
- **Lost case.** A case is in the baseline but not in the new run. A pass-rate number alone does not name a missing case. It is an error for critical cases and a warning for the rest.
- **New flakiness.** A case that was stable now gives mixed results over repeated runs. Warning only.
- **Overall drop.** Total pass rate falls by more than `--max-overall-drop` (default 2 points).

Exit code: 0 pass, 1 gate failed, 2 bad input.

## Input

JSONL, one result per line. `run` is optional. Repeat a case to record several runs.

```json
{"case": "refund-flow", "run": 1, "passed": true, "tags": ["critical"]}
```

## Run it

Needs Python 3.10+ and [uv](https://docs.astral.sh/uv/). There are no runtime dependencies.

```
uv sync
uv run eval-gate examples/baseline.jsonl examples/candidate.jsonl --out report.md
uv run pytest -q
```

The bundled example fails on purpose: a critical case drops from 5/5 to 4/5, another case is missing from the new run, and `tool-timeout-retry` falls from 100% to 60%.

## What was tested

- 12 offline pytest tests: zero tolerance on critical cases, `--max-drop` on others, lost cases, new flakiness, the overall gate, bad input, exit codes, and the bundled example's output.
- The tests run in GitHub Actions on every push (`.github/workflows/test.yml`).

## What was not tested

- Real eval output. Only the invented sample files were used. Other eval tools may need a small converter to this JSONL shape.
- Large files. Everything is read into memory.
- Statistical significance. A drop from 5/5 to 4/5 is flagged the same way as 50/50 to 40/50. With few runs per case, treat results as a signal, not proof.
- Scores or graded results. Only pass or fail is supported.
