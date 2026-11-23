#!/bin/sh
# Start/stop the background source-discovery job used to fill web/data sources.
#
# A pidfile is required: pkill -f 'cite_batch.py' also matches the command line
# of the very ssh session that runs it, which kills the caller instead.
#
#   scripts/run_cite.sh start|stop|status|tail
set -e
cd "$(dirname "$0")/.."
PY=/home/zjz/nongye/.venv/bin/python3.9
PID=.cite/cite.pid
LOG=.cite/cite.log
mkdir -p .cite

case "$1" in
  start)
    if [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; then
      echo "already running, pid $(cat "$PID")"; exit 0
    fi
    setsid nohup "$PY" scripts/cite_batch.py \
      --out .cite/sources.json --limit 6 --sleep 5 --tries 2 \
      < .cite/queries.tsv >> "$LOG" 2>&1 &
    echo $! > "$PID"
    echo "started, pid $(cat "$PID")"
    ;;
  stop)
    if [ -f "$PID" ]; then
      kill "$(cat "$PID")" 2>/dev/null && echo "stopped $(cat "$PID")" || echo "not running"
      rm -f "$PID"
    else
      echo "no pidfile"
    fi
    ;;
  status)
    if [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; then
      echo "running, pid $(cat "$PID")"
    else
      echo "not running"
    fi
    tail -3 "$LOG" 2>/dev/null || true
    "$PY" - <<'EOF'
import json, pathlib
p = pathlib.Path('.cite/sources.json')
if p.exists():
    d = json.loads(p.read_text(encoding='utf-8'))
    done = {k: v for k, v in d.items() if v}
    print(f"queries {len(d)}  with sources {len(done)}  empty {len(d) - len(done)}")
    print("empty:", ', '.join(k for k, v in d.items() if not v) or 'none')
EOF
    ;;
  tail)
    tail -15 "$LOG" 2>/dev/null || echo "no log yet"
    ;;
  *)
    echo "usage: $0 start|stop|status|tail"; exit 2
    ;;
esac
