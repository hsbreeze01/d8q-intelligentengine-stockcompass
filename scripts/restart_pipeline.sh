#!/usr/bin/env bash
# restart_pipeline.sh — Kill all existing pipeline daemon processes and start a fresh one.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="/var/log/d8q"
LOG_FILE="${LOG_DIR}/datapipeline.log"
DAEMON_CMD="pipeline.py --mode daemon"

# Ensure log directory exists
mkdir -p "${LOG_DIR}"

# Kill all existing daemon processes
echo "[restart] Stopping existing pipeline daemon processes..."
pids=$(pgrep -f "${DAEMON_CMD}" 2>/dev/null || true)
if [ -n "${pids}" ]; then
    echo "[restart] Killing PIDs: ${pids}"
    echo "${pids}" | xargs kill -9 2>/dev/null || true
    sleep 2
    # Verify they are gone
    remaining=$(pgrep -f "${DAEMON_CMD}" 2>/dev/null || true)
    if [ -n "${remaining}" ]; then
        echo "[restart] WARNING: some processes still alive: ${remaining}" >&2
        exit 1
    fi
else
    echo "[restart] No existing daemon processes found."
fi

# Start fresh daemon
echo "[restart] Starting new pipeline daemon..."
cd "${PROJECT_DIR}"
nohup /home/ecs-assist-user/d8q-intelligentengine-stockcompass/venv/bin/python scripts/pipeline.py --mode daemon >> "${LOG_FILE}" 2>&1 &
NEW_PID=$!
sleep 2

# Verify it started
if kill -0 "${NEW_PID}" 2>/dev/null; then
    echo "[restart] Pipeline daemon started successfully (PID=${NEW_PID})"
else
    echo "[restart] ERROR: Daemon process exited immediately. Check ${LOG_FILE}" >&2
    exit 1
fi
