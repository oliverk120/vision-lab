#!/usr/bin/env bash
# Manage the single Vision Lab Streamlit server for this workspace.
#
#   start    Start in the background unless already running (safe to repeat).
#   run      Run in this terminal (used by the "Run Vision Lab" launch option);
#            stops the background copy first so only one server exists.
#   stop     Stop the server started by this script.
#   restart  Stop, then start in the background.
#   status   Report whether the server is running and its address.
#   open     Open the website in a browser tab.
#   logs     Follow the background server's log.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${VISION_LAB_PORT:-8501}"
STATE="${VISION_LAB_STATE:-${XDG_STATE_HOME:-$HOME/.local/state}/vision-lab}"
PIDFILE="$STATE/streamlit-$PORT.pid"
LOG="$STATE/streamlit-$PORT.log"
mkdir -p "$STATE"

# One lock per port: concurrent start/run/stop calls cannot race each other.
exec 9>"$STATE/lock-$PORT"
flock -w 30 9 || { echo "Another Vision Lab command is still running; try again." >&2; exit 1; }

url() {
  if [[ -n "${CODESPACE_NAME:-}" && -n "${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-}" ]]; then
    echo "https://${CODESPACE_NAME}-${PORT}.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}"
  else
    echo "http://localhost:${PORT}"
  fi
}

our_pid() {  # PID recorded by this script, if that process is still alive.
  local pid
  pid="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then echo "$pid"; else rm -f "$PIDFILE"; fi
}

port_busy() { (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; }
healthy() { curl -fsS --max-time 2 "http://127.0.0.1:$PORT/_stcore/health" >/dev/null 2>&1; }

need_uv() {
  command -v uv >/dev/null || { echo "uv is not installed yet; wait for Codespace setup to finish." >&2; exit 1; }
}

refuse_foreign_port() {
  if port_busy; then
    echo "Port $PORT is already used by a process this script did not start:" >&2
    (lsof -nP -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true) >&2
    echo "Stop that process (or close its terminal) and try again." >&2
    exit 1
  fi
}

stop_server() {
  local pid pgid
  pid="$(our_pid)"
  [[ -z "$pid" ]] && return 0
  pgid="$(ps -o pgid= -p "$pid" | tr -d ' ')"
  # Background servers lead their own process group; foreground runs share the terminal's.
  if [[ "$pgid" == "$pid" ]]; then kill -TERM -- "-$pid" 2>/dev/null || true
  else pkill -TERM -P "$pid" 2>/dev/null || true; kill -TERM "$pid" 2>/dev/null || true; fi
  for _ in $(seq 50); do kill -0 "$pid" 2>/dev/null || break; sleep 0.2; done
  if kill -0 "$pid" 2>/dev/null; then
    [[ "$pgid" == "$pid" ]] && kill -KILL -- "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
  fi
  for _ in $(seq 25); do port_busy || break; sleep 0.2; done
  rm -f "$PIDFILE"
  echo "Vision Lab stopped."
}

start_server() {
  local pid
  pid="$(our_pid)"
  if [[ -n "$pid" ]]; then echo "Vision Lab is already running (PID $pid): $(url)"; return 0; fi
  refuse_foreign_port
  need_uv
  cd "$ROOT"
  echo "--- $(date -Is) starting Vision Lab on port $PORT" >>"$LOG"
  # setsid detaches the server from this shell so it survives Codespaces lifecycle hooks.
  setsid nohup uv run --locked streamlit run app/main.py --server.port "$PORT" >>"$LOG" 2>&1 </dev/null 9>&- &
  echo $! >"$PIDFILE"
  for _ in $(seq 240); do
    if healthy; then echo "Vision Lab is running: $(url)"; return 0; fi
    if ! kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      rm -f "$PIDFILE"; echo "Vision Lab failed to start. Last log lines:" >&2; tail -n 20 "$LOG" >&2; exit 1
    fi
    sleep 0.5
  done
  echo "Vision Lab is still starting; check progress with: scripts/vision-lab.sh logs" >&2
}

case "${1:-start}" in
  start) start_server ;;
  stop) stop_server ;;
  restart) stop_server; start_server ;;
  run)
    stop_server
    refuse_foreign_port
    need_uv
    cd "$ROOT"
    echo $$ >"$PIDFILE"   # exec keeps this PID, so start/stop recognise the foreground server.
    echo "Vision Lab will be available at $(url)  (Ctrl+C stops it)"
    exec 9>&-
    exec uv run --locked streamlit run app/main.py --server.port "$PORT"
    ;;
  status)
    pid="$(our_pid)"
    if [[ -n "$pid" ]] && healthy; then echo "Running (PID $pid): $(url)"
    elif [[ -n "$pid" ]]; then echo "Starting or unresponsive (PID $pid). Log: $LOG"
    elif port_busy; then echo "Port $PORT is used by a process this script did not start."
    else echo "Not running. Start it with: scripts/vision-lab.sh start"; fi
    ;;
  open)
    start_server >/dev/null
    target="$(url)"
    if [[ -n "${BROWSER:-}" ]]; then "$BROWSER" "$target"
    else echo "Open this address in your browser: $target"; fi
    ;;
  logs) touch "$LOG"; exec tail -n 100 -f "$LOG" ;;
  *) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
