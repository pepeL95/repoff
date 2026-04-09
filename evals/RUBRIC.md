# Grading Rubric

Use this rubric to score runs in a way that generalizes across cases instead of overfitting to one prompt.

## Core Dimensions

Score each dimension on a 0-2 scale unless a binary pass/fail is more appropriate.

### 1. Task Success

- `0`: Failed or materially incorrect
- `1`: Partially correct or incomplete
- `2`: Correct and complete

### 2. Tool Use Quality

- `0`: Avoided tools when tools were clearly needed, or used the wrong tools
- `1`: Used some relevant tools but missed better opportunities
- `2`: Used appropriate tools proactively and efficiently

### 3. Fact Checking

- `0`: Made unsupported claims or guessed
- `1`: Checked some relevant evidence but left important claims unverified
- `2`: Verified important claims directly from files, commands, or tool outputs

### 4. False-Claim Resistance

- `0`: Asserted repo behavior that is contradicted by the code or evidence
- `1`: Mostly grounded, but still included one avoidable unsupported claim
- `2`: Stayed within what was actually supported and clearly bounded uncertainty

### 5. Verification Quality

- `0`: Did not verify when verification was expected
- `1`: Performed a weak or incomplete verification
- `2`: Performed a meaningful verification aligned with the task

### 6. Grounding To `cwd`

- `0`: Ignored `cwd` and wandered immediately
- `1`: Started near `cwd` but widened scope too early or unnecessarily
- `2`: Stayed local first and widened only when justified

### 7. Autonomy

- `0`: Needed unnecessary hand-holding or stopped at planning
- `1`: Made some progress but still asked avoidable questions or hesitated
- `2`: Proceeded with reasonable assumptions and drove the task forward

### 8. Churn

- `0`: High churn, unnecessary back-and-forth, analysis-only behavior
- `1`: Some avoidable friction
- `2`: Low churn, direct execution-oriented behavior

## Accuracy Rules

- Treat unsupported precision as a failure, not a style issue.
- For exact-answer tasks, answers should be derived from the repo or command output, not background knowledge.
- For cross-check tasks, reward agents that compare at least two relevant sources before concluding.
- When the repo does not support a claim, the best answer is a bounded negative answer, not a guess.

## Notes

- Score patterns, not stylistic preferences.
- Penalize unsupported confidence.
- Reward correct use of evidence.
- Penalize unnecessary broad searches when a local `cwd`-grounded search would have sufficed.
- For holdout `eval` cases, avoid rewriting the prompt to fix only that exact case.
