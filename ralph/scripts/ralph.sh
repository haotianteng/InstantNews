#!/bin/bash
# Ralph v2 — Adversarial Agent Loop
#
# Directory layout:
#   ralph/scripts/ralph.sh           ← this file
#   ralph/scripts/CLAUDE.md          ← soul file (both roles)
#   ralph/scripts/TEAM_PROMPT.md     ← team lead prompt
#   ralph/scripts/format_stream.sh   ← stream-json formatter
#   ralph/scripts/skills/            ← skill definitions
#   ralph/prd.json                   ← story state
#   ralph/progress.txt               ← append-only log
#   ralph/test_results/              ← persistent test artifacts
#   ralph/session_logs/              ← per-iteration JSONL logs
#   ralph/archive/                   ← previous run archives
#
# Modes:
#   --mode team   Agent Teams (lead spawns implementor + tester)
#   --mode loop   Bash loop (alternates implementor ↔ tester)
#
# tmux: auto-splits into left (dashboard) + right (claude stream).
#   --no-tmux     Disable split even inside tmux
#
# Usage:
#   ./ralph/scripts/ralph.sh
#   ./ralph/scripts/ralph.sh --mode team
#   ./ralph/scripts/ralph.sh --mode loop --max-iterations 50
#   ./ralph/scripts/ralph.sh --no-tmux

set -e

# ── Paths ────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RALPH_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_ROOT="$(cd "$RALPH_DIR/.." && pwd)"

PRD_FILE="$RALPH_DIR/prd.json"
PROGRESS_FILE="$RALPH_DIR/progress.txt"
ARCHIVE_DIR="$RALPH_DIR/archive"
TEST_RESULTS_DIR="$RALPH_DIR/test_results"
SESSION_LOGS_DIR="$RALPH_DIR/session_logs"
LAST_BRANCH_FILE="$RALPH_DIR/.last-branch"

TEAM_PROMPT="$SCRIPT_DIR/TEAM_PROMPT.md"
CLAUDE_MD="$SCRIPT_DIR/CLAUDE.md"
FORMAT_STREAM="$SCRIPT_DIR/format_stream.sh"

# Runtime files (gitignored)
SIGNAL_FILE="$RALPH_DIR/.claude_done"
PROMPT_FILE="$RALPH_DIR/.current_prompt"
STREAM_FILE="$RALPH_DIR/.stream.jsonl"
STATUS_FILE="$RALPH_DIR/.agent_status"

MODE="loop"
MODEL="opus"
MAX_ITERATIONS=30
USE_TMUX="auto"

# ── Parse arguments ──────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --mode)            MODE="$2"; shift 2 ;;
    --mode=*)          MODE="${1#*=}"; shift ;;
    --model)           MODEL="$2"; shift 2 ;;
    --model=*)         MODEL="${1#*=}"; shift ;;
    --max-iterations)  MAX_ITERATIONS="$2"; shift 2 ;;
    --no-tmux)         USE_TMUX="no"; shift ;;
    --tmux)            USE_TMUX="yes"; shift ;;
    *)
      if [[ "$1" =~ ^[0-9]+$ ]]; then MAX_ITERATIONS="$1"; fi
      shift
      ;;
  esac
done

if [[ "$MODE" != "team" && "$MODE" != "loop" ]]; then
  echo "Error: Invalid mode '$MODE'. Must be 'team' or 'loop'."
  exit 1
fi

# Resolve tmux
if [[ "$USE_TMUX" == "auto" ]]; then
  [ -n "$TMUX" ] && USE_TMUX="yes" || USE_TMUX="no"
fi
if [[ "$USE_TMUX" == "yes" && -z "$TMUX" ]]; then
  echo "Error: --tmux requested but not inside tmux. Run: tmux new -s ralph"
  exit 1
fi

# ── Validation ───────────────────────────────────────────────────────
[ ! -f "$PRD_FILE" ] && echo "Error: $PRD_FILE not found." && exit 1
[ ! -f "$CLAUDE_MD" ] && echo "Error: $CLAUDE_MD not found." && exit 1
[[ "$MODE" == "team" && ! -f "$TEAM_PROMPT" ]] && echo "Error: $TEAM_PROMPT not found." && exit 1
chmod +x "$FORMAT_STREAM" 2>/dev/null || true

# ── Install CLAUDE.md to project root ────────────────────────────────
PROJECT_CLAUDE_MD="$PROJECT_ROOT/CLAUDE.md"
if [ -f "$PROJECT_CLAUDE_MD" ]; then
  if grep -q "Ralph v2 — Adversarial Build" "$PROJECT_CLAUDE_MD" 2>/dev/null; then
    cp "$CLAUDE_MD" "$PROJECT_CLAUDE_MD"
  elif ! grep -q "Ralph v2 — Adversarial Build" "$PROJECT_CLAUDE_MD" 2>/dev/null; then
    echo -e "\n<!-- BEGIN RALPH V2 -->" >> "$PROJECT_CLAUDE_MD"
    cat "$CLAUDE_MD" >> "$PROJECT_CLAUDE_MD"
    echo "<!-- END RALPH V2 -->" >> "$PROJECT_CLAUDE_MD"
  fi
else
  cp "$CLAUDE_MD" "$PROJECT_CLAUDE_MD"
fi

# ── Agent Teams check ────────────────────────────────────────────────
if [[ "$MODE" == "team" ]]; then
  SETTINGS_FILE="$HOME/.claude/settings.json"
  if [ -f "$SETTINGS_FILE" ] && ! grep -q "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS" "$SETTINGS_FILE" 2>/dev/null; then
    echo "WARNING: Agent Teams may not be enabled. Add to $SETTINGS_FILE:"
    echo '  { "env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" } }'
  fi
fi

# ── Archive & branch ─────────────────────────────────────────────────
if [ -f "$LAST_BRANCH_FILE" ]; then
  CURRENT_BRANCH=$(jq -r '.branchName // empty' "$PRD_FILE" 2>/dev/null || echo "")
  LAST_BRANCH=$(cat "$LAST_BRANCH_FILE" 2>/dev/null || echo "")
  if [ -n "$CURRENT_BRANCH" ] && [ -n "$LAST_BRANCH" ] && [ "$CURRENT_BRANCH" != "$LAST_BRANCH" ]; then
    ARCHIVE_FOLDER="$ARCHIVE_DIR/$(date +%Y-%m-%d)-$(echo "$LAST_BRANCH" | sed 's|^ralph/||')"
    mkdir -p "$ARCHIVE_FOLDER"
    [ -f "$PRD_FILE" ] && cp "$PRD_FILE" "$ARCHIVE_FOLDER/"
    [ -f "$PROGRESS_FILE" ] && cp "$PROGRESS_FILE" "$ARCHIVE_FOLDER/"
  fi
fi
CURRENT_BRANCH=$(jq -r '.branchName // empty' "$PRD_FILE" 2>/dev/null || echo "")
[ -n "$CURRENT_BRANCH" ] && echo "$CURRENT_BRANCH" > "$LAST_BRANCH_FILE"

# ── Init progress ────────────────────────────────────────────────────
if [ ! -f "$PROGRESS_FILE" ]; then
  DESCRIPTION=$(jq -r '.description // "No description"' "$PRD_FILE")
  cat > "$PROGRESS_FILE" << EOF
# Ralph v2 Progress Log
Started: $(date)
PRD: $DESCRIPTION
Mode: Adversarial ($MODE)
---

## Codebase Patterns

---
EOF
fi
mkdir -p "$TEST_RESULTS_DIR"
mkdir -p "$SESSION_LOGS_DIR"

# ══════════════════════════════════════════════════════════════════════
#  FUNCTIONS
# ══════════════════════════════════════════════════════════════════════

all_done() {
  local T D
  T=$(jq '.userStories | length' "$PRD_FILE")
  D=$(jq '[.userStories[] | select(.status == "TEST_PASSED")] | length' "$PRD_FILE")
  [ "$T" -eq "$D" ]
}

pick_agent() {
  local r i
  r=$(jq '[.userStories[] | select(.status == "READY_FOR_TEST")] | length' "$PRD_FILE")
  [ "$r" -gt 0 ] && echo "tester" && return
  i=$(jq '[.userStories[] | select(.status == "REQUIRE_IMPLEMENT" or .status == "TEST_FAILED" or .status == null)] | length' "$PRD_FILE")
  [ "$i" -gt 0 ] && echo "implementor" && return
  echo "done"
}

# Returns the story ID that the agent will work on (same priority logic as the agent prompts)
pick_story_id() {
  local agent="$1"
  if [ "$agent" == "tester" ]; then
    jq -r '[.userStories[] | select(.status == "READY_FOR_TEST")] | sort_by(.priority) | first | .id // "unknown"' "$PRD_FILE" 2>/dev/null
  else
    # Implementor: TEST_FAILED first, then REQUIRE_IMPLEMENT, then null
    local failed
    failed=$(jq -r '[.userStories[] | select(.status == "TEST_FAILED")] | sort_by(.priority) | first | .id // empty' "$PRD_FILE" 2>/dev/null)
    if [ -n "$failed" ]; then
      echo "$failed"
    else
      jq -r '[.userStories[] | select(.status == "REQUIRE_IMPLEMENT" or .status == null)] | sort_by(.priority) | first | .id // "unknown"' "$PRD_FILE" 2>/dev/null
    fi
  fi
}

# Save .stream.jsonl to a persistent named log
# Usage: save_session_log <iteration> <agent> [story_id]
save_session_log() {
  local iter="$1" agent="$2" story_id="${3:-unknown}"
  local ts
  ts=$(date +%H%M%S)
  local log_name
  log_name=$(printf "%03d-%s-%s-%s.jsonl" "$iter" "$agent" "$story_id" "$ts")
  local dest="$SESSION_LOGS_DIR/$log_name"

  if [ -f "$STREAM_FILE" ] && [ -s "$STREAM_FILE" ]; then
    cp "$STREAM_FILE" "$dest"
    echo "Session log saved: $dest"
  else
    # Even if stream is empty, record that a session ran with no output
    echo '{"type":"ralph_meta","note":"empty session","iter":'"$iter"',"agent":"'"$agent"'","story":"'"$story_id"'"}' > "$dest"
    echo "WARNING: Empty session log saved: $dest"
  fi
}

make_implementor_prompt() {
  cat << 'PROMPT'
You are the **Implementor** agent in the Ralph v2 adversarial system.
Read CLAUDE.md for your full role definition under "Role: Implementor".

1. Read ralph/prd.json and ralph/progress.txt (Codebase Patterns first)
2. Check correct branch from prd.json branchName
3. Pick highest-priority story: TEST_FAILED first, then REQUIRE_IMPLEMENT, then null
4. If TEST_FAILED: inspect ralph/test_results/<story-id>/ before coding
5. Implement ONE story
6. Self-validate (typecheck, lint, test)
7. Commit: feat: [Story ID] - [Title]  (or fix: ... for rework)
8. Update ralph/prd.json: status → READY_FOR_TEST, write implementation_notes, files_changed
9. Append to ralph/progress.txt with environment notes for Tester

NEVER set passes to true. NEVER modify tester-owned fields. ONE story only.
PROMPT
}

make_tester_prompt() {
  cat << 'PROMPT'
You are the **Tester** agent in the Ralph v2 adversarial system.
Read CLAUDE.md for your full role definition under "Role: Tester".

1. Read ralph/prd.json — find stories with status: READY_FOR_TEST
2. Read ralph/progress.txt — check Implementor's environment notes
3. Pick highest-priority READY_FOR_TEST story
4. mkdir -p ralph/test_results/<story-id>/attempt-<N>/
5. Execute REAL validation for EVERY acceptance criterion — capture output to test results dir
6. Verify test_assertions by execution, not by reading code
7. Run project quality checks — capture output
8. ALL pass → TEST_PASSED, passes: true. ANY fail → TEST_FAILED, fail_count++

NEVER modify source code. Save ALL artifacts to ralph/test_results/, NEVER /tmp.
ONE story only. If ALL stories TEST_PASSED, reply: <promise>COMPLETE</promise>
PROMPT
}

# ── Dashboard ─────────────────────────────────────────────────────────
render_dashboard() {
  local ITER="$1" AGENT="$2" STATE="$3"

  clear

  # Get actual pane width
  local PW
  PW=$(tput cols 2>/dev/null || echo 40)
  local IW=$(( PW - 4 ))   # inner width (minus "│  " prefix and " │" suffix)
  [ "$IW" -lt 20 ] && IW=20

  # Helper: draw a horizontal line with optional label
  hline() {
    local left="$1" right="$2" label="$3"
    if [ -z "$label" ]; then
      # Full line: ┌──────────┐
      printf '%s' "$left"
      printf '%0.s─' $(seq 1 $(( PW - 2 )))
      printf '%s\n' "$right"
    else
      # Labeled: ├── Label ──┤
      local label_section="── $label "
      local label_sec_len=$(( ${#label} + 4 ))
      local fill=$(( PW - 2 - label_sec_len ))
      [ "$fill" -lt 1 ] && fill=1
      printf '%s%s' "$left" "$label_section"
      printf '%0.s─' $(seq 1 $fill)
      printf '%s\n' "$right"
    fi
  }

  # Helper: print a row with right-aligned border
  row() {
    local text="$1"
    # Print left border + content, then jump to column PW and print right border
    printf '│ %b' "$text"
    printf '\033[%dG│\n' "$PW"
  }

  # Story title max chars
  local TITLE_MAX=$(( IW - 12 ))
  [ "$TITLE_MAX" -lt 10 ] && TITLE_MAX=10

  # ── Fetch data ──────────────────────────────────────────────────
  local T D F R O
  T=$(jq '.userStories | length' "$PRD_FILE" 2>/dev/null || echo 0)
  D=$(jq '[.userStories[] | select(.status == "TEST_PASSED")] | length' "$PRD_FILE" 2>/dev/null || echo 0)
  F=$(jq '[.userStories[] | select(.status == "TEST_FAILED")] | length' "$PRD_FILE" 2>/dev/null || echo 0)
  R=$(jq '[.userStories[] | select(.status == "READY_FOR_TEST")] | length' "$PRD_FILE" 2>/dev/null || echo 0)
  O=$(( T - D - F - R ))

  # Progress bar — fills available inner width minus label
  local PCT=0
  [ "$T" -gt 0 ] && PCT=$(( D * 100 / T ))
  local BAR_W=$(( IW - 8 ))  # room for " 100% "
  [ "$BAR_W" -lt 10 ] && BAR_W=10
  local FI=$(( PCT * BAR_W / 100 )) EM=$(( BAR_W - FI ))
  local BAR=""
  BAR=$(printf '█%.0s' $(seq 1 $FI 2>/dev/null))$(printf '░%.0s' $(seq 1 $EM 2>/dev/null))

  # Agent status from formatter
  local AGENT_DETAIL=""
  [ -f "$STATUS_FILE" ] && AGENT_DETAIL=$(cat "$STATUS_FILE" 2>/dev/null | head -1)

  # ── Draw ────────────────────────────────────────────────────────
  printf "\033[1m"
  hline "┌" "┐" ""
  row "Ralph v2 Dashboard"
  hline "├" "┤" ""
  printf "\033[0m"

  row "Mode:  $MODE / $MODEL"
  row "Iter:  $ITER / $MAX_ITERATIONS"
  row "Agent: $(printf '%-12s' "$(echo "$AGENT" | tr '[:lower:]' '[:upper:]')") $STATE"
  row ""
  row "$BAR $PCT%"
  row "✓ $D  ✗ $F  ⧖ $R  ○ $O"
  row ""

  # Live agent activity
  if [ -n "$AGENT_DETAIL" ]; then
    local ACT="${AGENT_DETAIL#agent_state=}"
    local ACT_MAX=$(( IW - 4 ))
    case "$ACT" in
      bash:*)   row "▶ $(echo "${ACT#bash:}" | cut -c1-$ACT_MAX)" ;;
      read:*)   row "📄 $(echo "${ACT#read:}" | cut -c1-$ACT_MAX)" ;;
      edit:*)   row "✏️  $(echo "${ACT#edit:}" | cut -c1-$ACT_MAX)" ;;
      tool:*)   row "🔧 $(echo "${ACT#tool:}" | cut -c1-$ACT_MAX)" ;;
      error)    row "✗ error occurred" ;;
      retry:*)  row "⟳ retrying..." ;;
      done)     row "✓ session complete" ;;
      idle)     row "· idle" ;;
      *)        row "· $(echo "$ACT" | cut -c1-$ACT_MAX)" ;;
    esac
    row ""
  fi

  hline "├" "┤" "Stories"

  # Per-story rows
  jq -r --argjson mx "$TITLE_MAX" '.userStories[] |
    .title[0:$mx] as $t |
    if .status == "TEST_PASSED" then "\u001b[32m✓\u001b[0m \(.id) \($t)"
    elif .status == "TEST_FAILED" then "\u001b[31m✗\u001b[0m \(.id) \($t) [\(.fail_count//0)x]"
    elif .status == "READY_FOR_TEST" then "\u001b[33m⧖\u001b[0m \(.id) \($t)"
    else "· \(.id) \($t)"
    end
  ' "$PRD_FILE" 2>/dev/null | while IFS= read -r story_line; do
    row "$story_line"
  done

  # Stuck warning
  local MF
  MF=$(jq '[.userStories[].fail_count // 0] | max' "$PRD_FILE" 2>/dev/null || echo 0)
  if [ "${MF:-0}" -ge 5 ]; then
    row ""
    row "\033[31m⚠  Story stuck (${MF}x fail)\033[0m"
  fi

  hline "├" "┤" "Recent"

  local RECENT_MAX=$(( IW - 2 ))
  tail -5 "$PROGRESS_FILE" 2>/dev/null | while IFS= read -r l; do
    row "$(echo "$l" | cut -c1-$RECENT_MAX)"
  done

  hline "└" "┘" ""
  echo ""
  if [[ "$MODE" == "team" ]]; then
    echo "  → Right pane: Agent Teams (interactive)"
    echo "  Ctrl-b →  switch to team"
    echo "  Shift+↓   navigate teammates"
  else
    echo "  → Right pane: Claude stream"
    echo "  Ctrl-b ←/→ switch panes"
  fi
}

show_status() {
  local T D F R
  T=$(jq '.userStories | length' "$PRD_FILE")
  D=$(jq '[.userStories[] | select(.status == "TEST_PASSED")] | length' "$PRD_FILE")
  F=$(jq '[.userStories[] | select(.status == "TEST_FAILED")] | length' "$PRD_FILE")
  R=$(jq '[.userStories[] | select(.status == "READY_FOR_TEST")] | length' "$PRD_FILE")
  echo "═══ Ralph v2: $D/$T passed  ✗ $F  ⧖ $R ═══"
}

# ══════════════════════════════════════════════════════════════════════
#  TMUX PANE MANAGEMENT
# ══════════════════════════════════════════════════════════════════════

RIGHT_PANE=""

setup_tmux() {
  # Get total window width in columns
  local TOTAL_W
  TOTAL_W=$(tmux display-message -p '#{window_width}')

  # 40% left (dashboard), 60% right (claude stream)
  local RIGHT_PCT=60
  local LEFT_COLS=$(( TOTAL_W * 40 / 100 ))

  # Enforce minimums: left at least 36 cols, right at least 60 cols
  if [ "$LEFT_COLS" -lt 36 ]; then
    RIGHT_PCT=$(( 100 - (3600 / TOTAL_W) ))
    [ "$RIGHT_PCT" -gt 90 ] && RIGHT_PCT=90
  fi
  if [ $(( TOTAL_W - LEFT_COLS )) -lt 60 ]; then
    RIGHT_PCT=60
  fi

  RIGHT_PANE=$(tmux split-window -h -p "$RIGHT_PCT" -d -P -F '#{pane_id}' "exec bash --norc")
  sleep 0.5
  tmux send-keys -t "$RIGHT_PANE" "cd '$PROJECT_ROOT' && clear" Enter
  sleep 0.3
}

teardown_tmux() {
  [ -n "$RIGHT_PANE" ] && tmux kill-pane -t "$RIGHT_PANE" 2>/dev/null || true
  rm -f "$SIGNAL_FILE" "$PROMPT_FILE" "$STATUS_FILE" "$STREAM_FILE"
}

# Launch claude with stream-json in right pane (loop mode only)
run_loop_tmux() {
  local ITER="$1" AGENT="$2" PROMPT_SOURCE="$3"

  rm -f "$SIGNAL_FILE" "$STREAM_FILE" "$STATUS_FILE"
  : > "$STREAM_FILE"
  echo "agent_state=starting" > "$STATUS_FILE"

  # Write prompt to file
  echo "$PROMPT_SOURCE" > "$PROMPT_FILE"

  # IMPORTANT: use `cat file | claude` not `claude < file`
  # stdin redirection via < conflicts with tmux PTY — claude gets
  # empty stdin, exits immediately, and the loop spins.
  local CLAUDE_CMD="RALPH_STATUS_FILE='$STATUS_FILE' cat '$PROMPT_FILE' \
    | claude -p \
    --model '$MODEL' \
    --effort max \
    --dangerously-skip-permissions \
    --output-format stream-json \
    --verbose \
    --include-partial-messages \
    2>&1 \
    | tee '$STREAM_FILE' \
    | '$FORMAT_STREAM'"

  tmux send-keys -t "$RIGHT_PANE" "clear && $CLAUDE_CMD ; echo \$? > '$SIGNAL_FILE'" Enter

  # Dashboard loop while waiting
  while [ ! -f "$SIGNAL_FILE" ]; do
    render_dashboard "$ITER" "$AGENT" "running"
    sleep 3
  done

  render_dashboard "$ITER" "$AGENT" "done"
  sleep 1
  rm -f "$SIGNAL_FILE"
}

# Launch claude interactively in right pane (team mode)
# Interactive mode lets Agent Teams spawn visible teammate panes.
# The left pane polls prd.json — no stream-json parsing needed.
run_team_tmux() {
  local SESSION_NUM="$1"

  rm -f "$SIGNAL_FILE" "$STATUS_FILE"
  echo "agent_state=team_lead" > "$STATUS_FILE"

  # Use --append-system-prompt-file to inject the team prompt safely
  # (avoids $(cat) quoting issues through tmux send-keys).
  # Short initial message as argument triggers the lead to start.
  tmux send-keys -t "$RIGHT_PANE" \
    "clear && cd '$PROJECT_ROOT' && claude \
      --model '$MODEL' \
      --dangerously-skip-permissions \
      --append-system-prompt-file '$TEAM_PROMPT' \
      'Begin. Read ralph/prd.json and start the adversarial implementor/tester loop.' \
      ; echo \$? > '$SIGNAL_FILE'" Enter

  # Dashboard loop — poll prd.json for progress, no stream to parse
  while [ ! -f "$SIGNAL_FILE" ]; do
    # Check if all done while team is still running
    if all_done; then
      render_dashboard "$SESSION_NUM" "team" "ALL PASSED"
      # Give the lead a moment to wrap up, then signal
      sleep 5
      if [ ! -f "$SIGNAL_FILE" ]; then
        # Team lead hasn't exited yet — send /exit
        tmux send-keys -t "$RIGHT_PANE" "/exit" Enter 2>/dev/null || true
        sleep 2
      fi
      break
    fi
    render_dashboard "$SESSION_NUM" "team" "running"
    sleep 4
  done

  render_dashboard "$SESSION_NUM" "team" "session ended"

  # Capture the team lead's scrollback as session log
  local log_dest="$SESSION_LOGS_DIR/$(printf '%03d' "$SESSION_NUM")-team-session.log"
  tmux capture-pane -t "$RIGHT_PANE" -p -S - > "$log_dest" 2>/dev/null || true
  [ -s "$log_dest" ] && echo "Team session log: $log_dest"

  sleep 1
  rm -f "$SIGNAL_FILE"
}

# ══════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════

if all_done; then
  show_status
  echo "All stories already passed!"
  exit 0
fi

# ── TMUX MODE ─────────────────────────────────────────────────────────
if [[ "$USE_TMUX" == "yes" ]]; then

  trap teardown_tmux EXIT
  setup_tmux

  if [[ "$MODE" == "team" ]]; then
    for s in $(seq 1 $MAX_ITERATIONS); do
      all_done && { render_dashboard "$s" "none" "COMPLETE"; exit 0; }
      run_team_tmux "$s"
      # Session log captured inside run_team_tmux via tmux capture-pane
      all_done && { render_dashboard "$s" "none" "COMPLETE"; exit 0; }
      sleep 3
    done
    render_dashboard "$MAX_ITERATIONS" "none" "MAX ITER"
    exit 1
  fi

  # Loop mode
  for i in $(seq 1 $MAX_ITERATIONS); do
    all_done && { render_dashboard "$i" "none" "COMPLETE"; exit 0; }
    AGENT=$(pick_agent)
    [ "$AGENT" == "done" ] && { render_dashboard "$i" "none" "COMPLETE"; exit 0; }

    STORY_ID=$(pick_story_id "$AGENT")

    if [ "$AGENT" == "implementor" ]; then
      PROMPT=$(make_implementor_prompt)
    else
      PROMPT=$(make_tester_prompt)
    fi

    run_loop_tmux "$i" "$AGENT" "$PROMPT"
    save_session_log "$i" "$AGENT" "$STORY_ID"

    # Check completion from stream
    if grep -q '"<promise>COMPLETE</promise>"' "$STREAM_FILE" 2>/dev/null || \
       grep -q 'COMPLETE' "$STREAM_FILE" 2>/dev/null; then
      all_done && { render_dashboard "$i" "none" "COMPLETE"; exit 0; }
    fi

    sleep 2
  done

  render_dashboard "$MAX_ITERATIONS" "none" "MAX ITER"
  exit 1
fi

# ── NON-TMUX MODE ────────────────────────────────────────────────────
show_status
echo ""

if [[ "$MODE" == "team" ]]; then
  echo "Mode: Agent Teams (interactive)"
  echo "Claude will spawn teammate panes. Use Shift+Down to navigate."
  echo ""
  for s in $(seq 1 $MAX_ITERATIONS); do
    all_done && { echo "All stories passed!"; show_status; exit 0; }
    echo "═══ Team session $s ═══"
    cd "$PROJECT_ROOT"
    # Run interactively — Agent Teams needs interactive mode to display teammates.
    claude --model "$MODEL" --dangerously-skip-permissions \
      --append-system-prompt-file "$TEAM_PROMPT" \
      "Begin. Read ralph/prd.json and start the adversarial implementor/tester loop." || true
    # No stream-json in interactive mode — log a marker
    echo '{"type":"ralph_meta","note":"interactive team session","session":'"$s"'}' \
      > "$SESSION_LOGS_DIR/$(printf '%03d' "$s")-team-interactive.jsonl"
    echo ""
    show_status
    all_done && { echo "All stories passed!"; exit 0; }
    echo "Session ended. Restarting in 3s..."
    sleep 3
  done
  exit 1
fi

for i in $(seq 1 $MAX_ITERATIONS); do
  all_done && { echo "All stories passed at iteration $i!"; show_status; exit 0; }
  AGENT=$(pick_agent)
  [ "$AGENT" == "done" ] && { echo "All stories passed!"; show_status; exit 0; }

  STORY_ID=$(pick_story_id "$AGENT")

  echo ""
  echo "═══ Iteration $i / $MAX_ITERATIONS — $(echo "$AGENT" | tr '[:lower:]' '[:upper:]') — $STORY_ID ═══"

  cd "$PROJECT_ROOT"

  if [ "$AGENT" == "implementor" ]; then
    PROMPT=$(make_implementor_prompt)
  else
    PROMPT=$(make_tester_prompt)
  fi

  : > "$STREAM_FILE"
  echo "$PROMPT" | claude -p --model "$MODEL" --effort max --dangerously-skip-permissions \
    --output-format stream-json --verbose --include-partial-messages \
    2>&1 \
    | tee "$STREAM_FILE" \
    | "$FORMAT_STREAM" || true

  save_session_log "$i" "$AGENT" "$STORY_ID"

  # Check completion
  if grep -q 'COMPLETE' "$STREAM_FILE" 2>/dev/null; then
    all_done && { echo "Ralph completed all tasks!"; show_status; exit 0; }
  fi

  # Stuck detection
  MF=$(jq '[.userStories[].fail_count // 0] | max' "$PRD_FILE" 2>/dev/null || echo 0)
  [ "${MF:-0}" -ge 5 ] && echo "⚠ Story stuck at ${MF}x failures."

  show_status
  sleep 3
done

echo "Reached max iterations ($MAX_ITERATIONS)."
show_status
exit 1