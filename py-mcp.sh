#!/data/data/com.termux/files/usr/bin/bash

SOURCE="${BASH_SOURCE[0]:-$0}"
while [ -h "$SOURCE" ]; do
  DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"

if [ "$DIR" = "/data/data/com.termux/files/usr/bin" ]; then
    DIR="/data/data/com.termux/files/home/PyPhone-MCP-Server"
fi

PYTHON_BIN="/data/data/com.termux/files/usr/bin/python3"
PID_FILE="$DIR/py-mcp.pid"
LOG_FILE="$DIR/py-mcp.log"
PORT=3000

get_ip() {
    "$PYTHON_BIN" -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('8.8.8.8', 80)); print(s.getsockname()[0]); s.close()" 2>/dev/null || echo "127.0.0.1"
}

is_running() {
    if [ -f "$PID_FILE" ]; then
        local pid
        pid=$(cat "$PID_FILE" 2>/dev/null)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
    fi
    if pgrep -f "python3 -m src.server" >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

print_endpoints() {
    local pid="$1"
    local lan_ip
    lan_ip=$(get_ip)
    echo "[py-mcp] 服务运行中 (PID: $pid)"
    echo "  - 本地端点:   http://127.0.0.1:$PORT/mcp"
    if [ -n "$lan_ip" ] && [ "$lan_ip" != "127.0.0.1" ]; then
        echo "  - 局域网端点: http://$lan_ip:$PORT/mcp"
    fi
}

start() {
    if is_running; then
        local pid
        pid=$(cat "$PID_FILE" 2>/dev/null || pgrep -f "python3 -m src.server" | head -n 1)
        print_endpoints "$pid"
        return 0
    fi
    echo "[py-mcp] 正在启动 Python MCP 服务..."
    daemonize -c "$DIR" -o "$LOG_FILE" -e "$LOG_FILE" -p "$PID_FILE" "$PYTHON_BIN" -m src.server
    sleep 1
    if is_running; then
        local pid
        pid=$(cat "$PID_FILE" 2>/dev/null)
        print_endpoints "$pid"
    else
        echo "[py-mcp] 启动失败，请检查日志: $LOG_FILE"
        [ -f "$LOG_FILE" ] && tail -n 15 "$LOG_FILE"
        return 1
    fi
}

stop() {
    if ! is_running; then
        echo "[py-mcp] 服务未运行"
        rm -f "$PID_FILE" 2>/dev/null
        return 0
    fi
    echo "[py-mcp] 正在停止 Python MCP 服务..."
    if [ -f "$PID_FILE" ]; then
        local pid
        pid=$(cat "$PID_FILE" 2>/dev/null)
        if [ -n "$pid" ]; then
            kill "$pid" 2>/dev/null || true
        fi
        rm -f "$PID_FILE" 2>/dev/null
    fi
    pkill -f "python3 -m src.server" 2>/dev/null || true

    local count=0
    while is_running && [ $count -lt 30 ]; do
        sleep 0.1
        count=$((count + 1))
    done

    if is_running; then
        pkill -9 -f "python3 -m src.server" 2>/dev/null || true
        sleep 0.1
    fi
    echo "[py-mcp] 服务已停止"
}

restart() {
    if ! is_running; then
        start
        return $?
    fi
    stop
    start
}

status() {
    if is_running; then
        local pid
        pid=$(cat "$PID_FILE" 2>/dev/null || pgrep -f "python3 -m src.server" | head -n 1)
        print_endpoints "$pid"
        return 0
    else
        echo "[py-mcp] 状态: 未运行"
        return 1
    fi
}

logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -n "${1:-30}" -f "$LOG_FILE"
    else
        echo "[py-mcp] 暂无日志文件: $LOG_FILE"
    fi
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    log|logs)
        logs "${2:-30}"
        ;;
    *)
        echo "用法: py-mcp {start|stop|restart|status|logs}"
        exit 1
        ;;
esac
