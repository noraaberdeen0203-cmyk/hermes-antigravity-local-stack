#!/usr/bin/env bash
set -u

STATUS_PANEL_HOME="${STATUS_PANEL_HOME:-${HERMES_HOME:-$HOME/.hermes}/status-panel}"
STATUS_PANEL_PYTHON="${STATUS_PANEL_PYTHON:-python3}"
PIDFILE="$STATUS_PANEL_HOME/status-panel.pid"
LOGFILE="$STATUS_PANEL_HOME/status-panel.log"
LOCKFILE="$STATUS_PANEL_HOME/start.lock"

mkdir -p "$STATUS_PANEL_HOME"
chmod 700 "$STATUS_PANEL_HOME"

exec 9>"$LOCKFILE"
if ! flock -n 9; then
    exit 0
fi

if [ -f "$PIDFILE" ]; then
    old_pid="$(<"$PIDFILE")"
    if [[ "$old_pid" =~ ^[0-9]+$ ]] && kill -0 "$old_pid" 2>/dev/null; then
        exit 0
    fi
    rm -f -- "$PIDFILE"
fi

if ss -ltn 2>/dev/null | grep -q '127.0.0.1:9120 '; then
    echo "PORT_CONFLICT: 127.0.0.1:9120 is already occupied" >&2
    exit 3
fi

cd "$STATUS_PANEL_HOME"
setsid "$STATUS_PANEL_PYTHON" "$STATUS_PANEL_HOME/server.py" </dev/null >>"$LOGFILE" 2>&1 &
child_pid=$!
printf '%s\n' "$child_pid" > "$PIDFILE"
chmod 600 "$PIDFILE" "$LOGFILE" "$LOCKFILE"
exit 0
