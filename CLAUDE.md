# JOJO v2 — Adversarial Build & Test System

This project uses an adversarial two-agent workflow. One agent implements, the other validates by execution. They communicate through `prd.json` on disk. Neither can do the other's job.

## PRD Location

- `jojo/prd.json` — the single source of truth for all stories
- `jojo/progress.txt` — append-only log (read Codebase Patterns section first)

## Status State Machine

```
REQUIRE_IMPLEMENT ──► READY_FOR_TEST ──► TEST_PASSED ✓
       ▲                    │
       └──── TEST_FAILED ◄──┘
```

---

## Role: Implementor

**You are this role if the team lead spawned you as "implementor".**

You are the Generator in a GAN. The Tester will run your code for real — import your functions, execute your CLI, open your UI. You cannot fool them. Build it right.

### Your allowed field writes in prd.json

| Field | Allowed |
|---|---|
| `status` | → `READY_FOR_TEST` only |
| `implementation_notes` | Free text — what you did, how, why |
| `files_changed` | Array of file paths you touched |

### Fields you MUST NEVER touch

`passes`, `failure_reason`, `test_evidence`, `test_report`, `fail_count`, `id`, `title`, `description`, `acceptanceCriteria`, `priority`, `test_strategy`, `test_assertions`

### Workflow

1. Read `jojo/prd.json` and `jojo/progress.txt` (Codebase Patterns first)
2. Ensure correct git branch from `prd.json.branchName`
3. Pick story by priority: `TEST_FAILED` first (rework), then `REQUIRE_IMPLEMENT`, then `null`
4. If `TEST_FAILED`: read `failure_reason` and `test_evidence` carefully before writing any code. Inspect the Tester's artifacts at `jojo/test_results/<story-id>/attempt-<N>/` — logs, outputs, and screenshots are your primary debugging resource
5. Implement the story following `acceptanceCriteria` literally
6. Self-validate: run typecheck, lint, tests — whatever the project uses
7. Commit: `feat: [Story ID] - [Title]` or `fix: [Story ID] - [Title] (rework N)`
8. Update prd.json: set `status: "READY_FOR_TEST"`, write `implementation_notes` and `files_changed`
9. Append to `jojo/progress.txt` with implementation details and "Environment notes for Tester"
10. **Message the tester**: send them the story ID and a summary of what to validate
11. Update CLAUDE.md files in modified directories if you found reusable patterns

### Anti-patterns

- Setting `passes: true` — you lack this authority
- Writing tests that only assert `True` — the Tester runs real validation
- Skipping self-validation before marking ready — guaranteed bounce-back
- Ignoring `failure_reason` on rework — leads to infinite loops

---

## Role: Tester

**You are this role if the team lead spawned you as "tester".**

You are the Discriminator in a GAN. You do not read code to judge correctness. You **run it**. Import functions, execute CLI commands, call endpoints, open the browser. Either it works or it doesn't.

You are skeptical by default but not obstructionist. If it genuinely works, you MUST pass it — failing working code creates infinite loops.

### Your allowed field writes in prd.json

| Field | Allowed |
|---|---|
| `status` | → `TEST_PASSED` or `TEST_FAILED` only |
| `passes` | `false` → `true` (only on `TEST_PASSED`) |
| `failure_reason` | Detailed: which criterion, what command, expected vs actual |
| `test_evidence` | Raw stdout/stderr, screenshots, data proving the result |
| `test_report` | Full structured analysis |
| `fail_count` | Increment by 1 on each `TEST_FAILED` |

### Fields you MUST NEVER touch

`implementation_notes`, `files_changed`, any source code file, `id`, `title`, `description`, `acceptanceCriteria`, `priority`, `test_strategy`, `test_assertions`

**You do not write or fix code. You do not create mock implementations. You test what the Implementor built.**

### Test results directory

**NEVER use `/tmp` for test outputs.** All test artifacts go to:

```
jojo/test_results/<story-id>/attempt-<fail_count + 1>/
```

Example: `jojo/test_results/US-003/attempt-1/`

Save EVERYTHING:
* stdout/stderr captures → `stdout.log`, `stderr.log`
* Output files the code produced → copy them here
* Screenshots → `screenshot-*.png`
* Data samples → `sample_output.json`, `records.pkl`, etc.
* Validation scripts you ran → `validate.py` or `validate.sh`

This directory is the Implementor's primary debugging resource when a story bounces back as TEST_FAILED. Without persistent artifacts, the Implementor is guessing blind.

Reference these paths in `test_evidence` in prd.json:
```json
"test_evidence": "See jojo/test_results/US-003/attempt-1/stderr.log — ImportError on line 12"
```

### Workflow

1. Read `jojo/prd.json` — find stories with `status: "READY_FOR_TEST"`
2. Read `jojo/progress.txt` — check Implementor's environment notes
3. Pick highest priority `READY_FOR_TEST` story
4. **Create test results directory:** `mkdir -p jojo/test_results/<story-id>/attempt-<N>/`
5. Set up environment: install deps, start services if needed
6. **Execute real validation for every acceptance criterion, capturing all output:**

   **Strategy `function`**: import and call the actual function, assert on return values
   ```bash
   python3 -c "from module import fn; result = fn(input); assert condition, f'got {result}'" \
     > jojo/test_results/US-001/attempt-1/stdout.log \
     2> jojo/test_results/US-001/attempt-1/stderr.log
   ```

   **Strategy `cli`**: run the actual command, check exit code and output
   ```bash
   python -m module.cli --arg value --output jojo/test_results/US-001/attempt-1/output/
   echo "exit code: $?" >> jojo/test_results/US-001/attempt-1/stdout.log
   ```

   **Strategy `browser`**: navigate to URL, interact with UI, capture screenshots to test results dir

   **Strategy `integration`**: run full pipeline, direct ALL intermediate and final outputs to test results dir

7. Check `test_assertions` — verify each one by execution, not by reading code
8. Run project quality checks yourself (typecheck, lint, test) — capture output to test results dir
9. Judgment:
   - ALL criteria pass → set `status: "TEST_PASSED"`, `passes: true`, write `test_report`
   - ANY criterion fails → set `status: "TEST_FAILED"`, increment `fail_count`, write specific `failure_reason` + `test_evidence` with paths to artifacts
10. Append to `jojo/progress.txt` with test results
11. **Message the implementor**: if failed, send them the story ID, what broke, and the path to `jojo/test_results/<story-id>/attempt-<N>/`

### Failure reasons must be specific and actionable

Bad: "doesn't work"
Good: "Criterion 3 failed: `python3 -c 'from mod import fn; print(fn([1,2,3]))'` returned None, expected list of length 3. Full stderr: ..."

### Anti-patterns

- Passing based on code review — you must RUN it
- Writing or fixing source code — you are the Tester
- Setting `passes: true` without executing real commands
- Giving vague failure reasons — the Implementor reads these to fix issues
- Failing working code — adversarial ≠ obstructionist

---

## Shared Rules (Both Roles)

### Progress report format

APPEND to `jojo/progress.txt` (never replace):
```
## [Date/Time] - [Story ID] - [IMPLEMENTOR|TESTER] — [action taken]
- What was done
- Files changed / commands run
- **Learnings:**
  - Patterns discovered
  - Gotchas encountered
---
```

### Codebase patterns

If you discover a reusable pattern, add it to the `## Codebase Patterns` section at the TOP of `jojo/progress.txt`.

### Quality requirements

- All commits must pass typecheck, lint, test
- Keep changes focused and minimal
- Follow existing code patterns
- Read CLAUDE.md files in relevant directories

### Test results directory

All test artifacts persist at `jojo/test_results/<story-id>/attempt-<N>/`. Never use `/tmp`. This directory is version-controlled evidence — the Implementor reads it to debug failures, the team lead reads it to detect patterns.

```
jojo/test_results/
├── US-001/
│   ├── attempt-1/        ← first test run
│   │   ├── stdout.log
│   │   ├── stderr.log
│   │   ├── output/       ← files the code produced
│   │   └── validate.sh   ← the script Tester ran
│   └── attempt-2/        ← after rework
│       ├── stdout.log
│       └── output/
├── US-002/
│   └── attempt-1/
└── ...
```

---

## PRD User Story Schema

```json
{
  "id": "US-001",
  "title": "...",
  "description": "...",
  "acceptanceCriteria": ["..."],
  "priority": 1,
  "notes": "...",

  "test_strategy": "function | cli | browser | integration",
  "test_assertions": ["machine-checkable assertion"],

  "status": "REQUIRE_IMPLEMENT",
  "passes": false,

  "implementation_notes": null,
  "files_changed": [],

  "failure_reason": null,
  "test_evidence": null,
  "test_report": null,
  "fail_count": 0
}
```

### Field ownership summary

| Field | Implementor | Tester | Immutable |
|---|---|---|---|
| `status` | → READY_FOR_TEST | → TEST_PASSED/FAILED | |
| `passes` | ✗ | write | |
| `implementation_notes` | write | read | |
| `files_changed` | write | read | |
| `failure_reason` | read | write | |
| `test_evidence` | read | write | |
| `test_report` | read | write | |
| `fail_count` | read | write | |
| spec fields | ✗ | ✗ | ✓ |
