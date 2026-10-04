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
    # 1. 启动 MCP 主服务
    if is_running; then
        local pid
        pid=$(cat "$PID_FILE" 2>/dev/null || pgrep -f "python3 -m src.server" | head -n 1)
        print_endpoints "$pid"
    else
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
        fi
    fi

    # 2. 启动 WebUI
    local webui_pids
    webui_pids=$(ps aux | grep "[p]ython -m src.webui" | awk '{print $2}')
    if [ -z "$webui_pids" ]; then
        echo "[py-mcp] 正在启动 MCP 审批 WebUI..."
        daemonize -c "$DIR" -o "$DIR/webui.log" -e "$DIR/webui.log" "$PYTHON_BIN" -m src.webui
        echo "  - WebUI 端点: http://127.0.0.1:8080"
    else
        echo "[py-mcp] MCP 审批 WebUI 已在运行"
        echo "  - WebUI 端点: http://127.0.0.1:8080"
    fi
    return 0
}

stop() {
    # 1. 停止 MCP 主服务
    if ! is_running; then
        echo "[py-mcp] 服务未运行"
        rm -f "$PID_FILE" 2>/dev/null
    else
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
    fi

    # 2. 停止 WebUI
    local webui_pids
    webui_pids=$(ps aux | grep "[p]ython -m src.webui" | awk '{print $2}')
    if [ -n "$webui_pids" ]; then
        echo "[py-mcp] 正在停止 MCP 审批 WebUI..."
        kill -9 $webui_pids 2>/dev/null || true
        echo "[py-mcp] WebUI 已停止"
    fi
    
    return 0
}

restart() {
    stop
    start
}

status() {
    if is_running; then
        local pid
        pid=$(cat "$PID_FILE" 2>/dev/null || pgrep -f "python3 -m src.server" | head -n 1)
        print_endpoints "$pid"
    else
        echo "[py-mcp] 状态: 服务未运行"
    fi

    local webui_pids
    webui_pids=$(ps aux | grep "[p]ython -m src.webui" | awk '{print $2}')
    if [ -n "$webui_pids" ]; then
        echo "[py-mcp] 状态: WebUI 运行中"
        echo "  - WebUI 端点: http://127.0.0.1:8080"
    else
        echo "[py-mcp] 状态: WebUI 未运行"
    fi
    return 0
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
