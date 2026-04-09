# Evals

This directory treats harness development as an ML-style train/test/eval problem.

The goal is not just to improve prompts by intuition. The goal is to improve agent behavior against a fixed, repo-rooted dataset that captures the actual work patterns and failure modes of `repoff`.

## Split Intent

- `train.jsonl`
  Prompt-development and behavior-shaping cases. These are the cases we are allowed to look at while tuning the harness.

- `test.jsonl`
  Day-to-day regression checks while iterating on prompts, middleware, and harness behavior.

- `eval.jsonl`
  Holdout cases. These should be used more sparingly and treated as the closest thing to an unseen benchmark for this repository.

## What We Are Measuring

This dataset is designed to measure more than final text quality.

Primary behavior targets:

- autonomy
- proactive tool use
- low user/orchestrator churn
- repository grounding
- correct use of `cwd`
- verification discipline
- correct final outcome

## Case Schema

Each line in the dataset files is a JSON object with this shape:

```json
{
  "id": "unique-case-id",
  "split": "train|test|eval",
  "category": "inspection|edit|multi_step|autonomy|grounding|verification",
  "cwd": "repo-relative working directory",
  "prompt": "user prompt to send to the harness",
  "tags": ["autonomy", "tool_use"],
  "expectations": {
    "must_inspect_paths": ["repo-relative path"],
    "should_use_tools": ["grep", "read_file"],
    "must_edit_paths": ["repo-relative path"],
    "must_verify": true,
    "should_avoid_unnecessary_questions": true,
    "notes": "Human-readable grading guidance."
  }
}
```

## Grading Guidance

These cases are intended to be graded on both outcome and process.

Suggested dimensions:

- `task_success`
- `autonomy`
- `tool_use_quality`
- `grounding_to_cwd`
- `verification_quality`
- `churn`

## Usage Notes

- Keep cases rooted in this repository.
- Prefer realistic tasks over synthetic benchmark-style prompts.
- Add cases when a real failure mode appears in normal usage.
- Do not overfit the holdout `eval.jsonl` split.

## Next Steps

The current dataset is only the starting point.

Likely next additions:

- a grading rubric file
- a small results format for comparing harness revisions

## Eval Runner

Use the lightweight runner at [run_evals.py](/Users/pepelopez/Documents/Programming/repoff/evals/run_evals.py) to execute a split against the live harness.

The runner:

- loads one split
- runs each prompt through `ChatService`
- sets `cwd` from the case definition
- writes isolated run state under `evals/results/<run-id>/state`
- stores machine-readable artifacts for later analysis

Artifacts written per run:

- `run_config.json`
- `bridge_health.json`
- `results.jsonl`
- `summary.json`
- `state/`
  Contains isolated session state and per-turn logs for that run only

## How To Initialize And Run

### 1. Start the VS Code LM bridge

In VS Code, with this repository open:

1. Reload the window if needed
2. Run `LM Bridge: Start Server`

### 2. Prepare the Python environment

```bash
conda env create -f backend/environment.yml
conda activate repoff
python -m pip install -r backend/requirements.txt
python -m pip install -e backend
```

### 3. Run a split

From the repo root:

```bash
/opt/homebrew/Caskroom/miniforge/base/envs/repoff/bin/python evals/run_evals.py --split train
```

Useful variants:

```bash
/opt/homebrew/Caskroom/miniforge/base/envs/repoff/bin/python evals/run_evals.py --split test
/opt/homebrew/Caskroom/miniforge/base/envs/repoff/bin/python evals/run_evals.py --split eval
/opt/homebrew/Caskroom/miniforge/base/envs/repoff/bin/python evals/run_evals.py --split test --limit 2
/opt/homebrew/Caskroom/miniforge/base/envs/repoff/bin/python evals/run_evals.py --split train --case-id train_autonomy_fix_without_handholding
```

If the bridge is on a different port:

```bash
/opt/homebrew/Caskroom/miniforge/base/envs/repoff/bin/python evals/run_evals.py --split test --port 8765
```

### 4. Share the results directory

After the run finishes, note the output directory under `evals/results/` and share:

- `summary.json`
- `results.jsonl`
- any relevant logs under `state/logs/`

That is enough for iterative analysis and prompt adjustment.

## Prompt-Tuning Discipline

When updating the system prompt based on results:

- optimize for patterns across cases, not one case at a time
- prefer changes that improve autonomy and tool use broadly
- do not overfit the holdout `eval.jsonl` split
- treat the `eval` split as the closest thing to an unseen benchmark
