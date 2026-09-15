#!/bin/bash
set -euo pipefail

export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATE="$(date +%Y-%m-%d)"

cd "$DIR"
python3 generate_digest.py || true
bash "$DIR/research_concept.sh" || true

SCRIPTS_DIR="$HOME/content-log/scripts"
CONCEPT_FILE="$SCRIPTS_DIR/$DATE-concept.md"

if [ -f "$CONCEPT_FILE" ]; then
  osascript -e "display notification \"Concept script ready. News digest sent to Telegram — reply there to pick today's topic.\" with title \"Daily AI Content\""
else
  osascript -e "display notification \"Check run_morning.err.log — something didn't generate today.\" with title \"Daily AI Content\""
fi
