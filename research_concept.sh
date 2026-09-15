#!/bin/bash
set -euo pipefail

export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATE="$(date +%Y-%m-%d)"

SCRIPTS_DIR="$HOME/content-log/scripts"
mkdir -p "$SCRIPTS_DIR"

TOPIC="$(python3 "$DIR/pop_concept.py")"

OUT_FILE="$SCRIPTS_DIR/$DATE-concept.md"

PROMPT="You are helping me prepare a short video I will film myself, teaching a concept to people learning about AI. Today's concept: \"$TOPIC\". Write:
1. A short suggested title (one line).
2. A spoken script of roughly 60-90 seconds (about 150-220 words) explaining this concept simply, with one concrete example or analogy, in my casual first-person voice, as if I'm talking to camera. No stage directions, just the words to say. Assume the viewer is smart but new to AI/ML terminology.
Output as markdown with headers for Title / Script."

echo "$TOPIC" | claude -p --no-session-persistence --disallowedTools Write Edit Bash NotebookEdit Agent WebFetch WebSearch -- "$PROMPT" > "$OUT_FILE"

echo "Concept script for '$TOPIC' written to $OUT_FILE"
