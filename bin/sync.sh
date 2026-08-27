#!/usr/bin/env bash
# Periodic entry point for cron. Loads .env, runs incremental sync, logs output.
set -euo pipefail
cd "$(dirname "$0")/.."
LOG_DIR="$(pwd)/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/sync-$(date +%F-%H%M).log"
set -a; [ -f .env ] && source .env; set +a
exec python3 -m weread_link "$@" >"$LOG_FILE" 2>&1
