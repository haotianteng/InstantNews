#!/bin/bash
# format_stream.sh — Formats Claude Code stream-json into readable terminal output
#
# Reads NDJSON from stdin (claude --output-format stream-json --verbose)
# Outputs colored, formatted text to stdout (right tmux pane)
# Writes agent status to $RALPH_STATUS_FILE for dashboard (left tmux pane)
#
# Usage:
#   claude -p --output-format stream-json --verbose --include-partial-messages \
#     | format_stream.sh

STATUS_FILE="${RALPH_STATUS_FILE:-}"

# ── Colors ────────────────────────────────────────────────────────────
C_RESET="\033[0m"
C_DIM="\033[2m"
C_BOLD="\033[1m"
C_CYAN="\033[36m"
C_BLUE="\033[34m"
C_GREEN="\033[32m"
C_YELLOW="\033[33m"
C_RED="\033[31m"
C_MAGENTA="\033[35m"
C_GRAY="\033[90m"

write_status() {
  if [ -n "$STATUS_FILE" ]; then
    echo "$1" > "$STATUS_FILE"
  fi
}

write_status "agent_state=starting"

# ── Process NDJSON line by line ───────────────────────────────────────
while IFS= read -r line; do
  # Skip empty lines
  [ -z "$line" ] && continue

  # Parse event type
  TYPE=$(echo "$line" | jq -r '.type // empty' 2>/dev/null)
  [ -z "$TYPE" ] && continue

  case "$TYPE" in

    # ── Streaming text deltas ──────────────────────────────────────
    stream_event)
      EVENT_TYPE=$(echo "$line" | jq -r '.event.type // empty' 2>/dev/null)

      case "$EVENT_TYPE" in
        content_block_delta)
          DELTA_TYPE=$(echo "$line" | jq -r '.event.delta.type // empty' 2>/dev/null)
          if [ "$DELTA_TYPE" == "text_delta" ]; then
            TEXT=$(echo "$line" | jq -r '.event.delta.text // empty' 2>/dev/null)
            printf '%b' "$TEXT"
          fi
          ;;

        content_block_start)
          BLOCK_TYPE=$(echo "$line" | jq -r '.event.content_block.type // empty' 2>/dev/null)
          if [ "$BLOCK_TYPE" == "tool_use" ]; then
            TOOL_NAME=$(echo "$line" | jq -r '.event.content_block.name // empty' 2>/dev/null)
            printf '\n%b── %s %b' "$C_CYAN$C_BOLD" "$TOOL_NAME" "$C_RESET"
            write_status "agent_state=tool:$TOOL_NAME"
          fi
          ;;

        content_block_stop)
          # End of a content block
          ;;
      esac
      ;;

    # ── Complete assistant message ─────────────────────────────────
    assistant)
      # Extract tool use info from complete messages
      TOOLS=$(echo "$line" | jq -r '
        .message.content[]?
        | select(.type == "tool_use")
        | .name
      ' 2>/dev/null)

      if [ -n "$TOOLS" ]; then
        for tool in $TOOLS; do
          case "$tool" in
            Bash|bash)
              CMD=$(echo "$line" | jq -r '
                .message.content[]?
                | select(.type == "tool_use" and .name == "Bash")
                | .input.command // .input.cmd // empty
              ' 2>/dev/null | head -1)
              printf '\n%b  ▶ bash: %s%b\n' "$C_CYAN" "$CMD" "$C_RESET"
              write_status "agent_state=bash:$(echo "$CMD" | cut -c1-60)"
              ;;

            Read|read|View|view)
              FILE=$(echo "$line" | jq -r '
                .message.content[]?
                | select(.type == "tool_use" and (.name == "Read" or .name == "View"))
                | .input.file_path // .input.path // empty
              ' 2>/dev/null | head -1)
              printf '%b  📄 read: %s%b\n' "$C_BLUE" "$FILE" "$C_RESET"
              write_status "agent_state=read:$(basename "$FILE" 2>/dev/null)"
              ;;

            Edit|edit|str_replace|Write|write)
              FILE=$(echo "$line" | jq -r '
                .message.content[]?
                | select(.type == "tool_use" and (.name == "Edit" or .name == "Write" or .name == "str_replace"))
                | .input.file_path // .input.path // empty
              ' 2>/dev/null | head -1)
              printf '%b  ✏️  edit: %s%b\n' "$C_YELLOW" "$FILE" "$C_RESET"
              write_status "agent_state=edit:$(basename "$FILE" 2>/dev/null)"
              ;;

            *)
              printf '%b  🔧 %s%b\n' "$C_MAGENTA" "$tool" "$C_RESET"
              write_status "agent_state=tool:$tool"
              ;;
          esac
        done
      fi

      # Show stop reason
      STOP=$(echo "$line" | jq -r '.message.stop_reason // empty' 2>/dev/null)
      if [ "$STOP" == "end_turn" ]; then
        printf '\n%b── end turn ──%b\n\n' "$C_DIM" "$C_RESET"
        write_status "agent_state=idle"
      fi
      ;;

    # ── Tool results ──────────────────────────────────────────────
    tool_result)
      IS_ERROR=$(echo "$line" | jq -r '.is_error // false' 2>/dev/null)
      if [ "$IS_ERROR" == "true" ]; then
        ERR=$(echo "$line" | jq -r '.content // empty' 2>/dev/null | head -3)
        printf '%b  ✗ error: %s%b\n' "$C_RED" "$ERR" "$C_RESET"
        write_status "agent_state=error"
      else
        # Show truncated result
        RESULT=$(echo "$line" | jq -r '
          if .content | type == "string" then .content
          elif .content | type == "array" then (.content[]? | .text // empty)
          else empty end
        ' 2>/dev/null | head -5)
        if [ -n "$RESULT" ]; then
          # Truncate long results
          RESULT_SHORT=$(echo "$RESULT" | head -3 | cut -c1-80)
          printf '%b  %s%b\n' "$C_GRAY" "$RESULT_SHORT" "$C_RESET"
        fi
      fi
      ;;

    # ── System events ─────────────────────────────────────────────
    system)
      SUBTYPE=$(echo "$line" | jq -r '.subtype // empty' 2>/dev/null)
      case "$SUBTYPE" in
        api_retry)
          ATTEMPT=$(echo "$line" | jq -r '.attempt // "?"' 2>/dev/null)
          DELAY=$(echo "$line" | jq -r '.retry_delay_ms // "?"' 2>/dev/null)
          printf '%b  ⟳ API retry %s (waiting %sms)%b\n' "$C_YELLOW" "$ATTEMPT" "$DELAY" "$C_RESET"
          write_status "agent_state=retry:$ATTEMPT"
          ;;
        *)
          ;;
      esac
      ;;

    # ── Result (final) ────────────────────────────────────────────
    result)
      printf '\n%b═══ Session complete ═══%b\n' "$C_GREEN$C_BOLD" "$C_RESET"
      # Extract cost info if available
      COST=$(echo "$line" | jq -r '.cost_usd // empty' 2>/dev/null)
      TOKENS_IN=$(echo "$line" | jq -r '.usage.input_tokens // empty' 2>/dev/null)
      TOKENS_OUT=$(echo "$line" | jq -r '.usage.output_tokens // empty' 2>/dev/null)
      if [ -n "$COST" ]; then
        printf '%b  Cost: $%s  Tokens: %s in / %s out%b\n' "$C_DIM" "$COST" "$TOKENS_IN" "$TOKENS_OUT" "$C_RESET"
      fi
      write_status "agent_state=done"
      ;;

  esac

done