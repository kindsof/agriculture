#!/bin/bash
# 检索 API 启停。纯标准库，用 /usr/bin/python3.9，不需要 venv。
#   ./corpus/run_api.sh start|stop|status|restart
set -u
cd "$(dirname "$0")/.."
PORT="${PORT:-52346}"
PY=/usr/bin/python3.9
PIDFILE=corpus/api.pid
LOG=corpus/api.log

alive() { [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; }

case "${1:-status}" in
  start)
    if alive; then echo "已在运行 PID $(cat $PIDFILE)"; exit 0; fi
    nohup "$PY" corpus/api.py --port "$PORT" >> "$LOG" 2>&1 &
    echo $! > "$PIDFILE"
    sleep 2
    if alive; then echo "已启动 PID $(cat $PIDFILE) 端口 $PORT"; else echo "启动失败"; tail -5 "$LOG"; exit 1; fi
    ;;
  stop)
    if alive; then kill "$(cat $PIDFILE)" && rm -f "$PIDFILE" && echo "已停止"; else echo "未运行"; fi
    ;;
  restart)
    "$0" stop; sleep 1; "$0" start
    ;;
  status)
    if alive; then echo "PID $(cat $PIDFILE) 端口 $PORT"; else echo "未运行"; exit 1; fi
    curl -s -m 5 "127.0.0.1:$PORT/api/health"; echo
    ;;
  *) echo "用法: $0 start|stop|restart|status"; exit 1 ;;
esac
