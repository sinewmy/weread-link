#!/usr/bin/env bash
# Periodic entry point for cron. Loads .env, runs incremental sync, logs output.
set -euo pipefail
cd "$(dirname "$0")/.."
LOGDIR="$(pwd)/logs"
mkdir -p "$LOGDIR"
set -a; [ -f .env ] && source .env; set +a
LOG_FILE="${WEREAD_LOG_FILE:-$LOGDIR/sync.log}"
exec python3 -m weread_link --log "$LOG_FILE"
