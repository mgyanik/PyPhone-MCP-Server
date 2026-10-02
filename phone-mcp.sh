#!/data/data/com.termux/files/usr/bin/bash
SERVER_DIR="/data/data/com.termux/files/home/PyPhone-MCP-Server"
SERVER_JS="$SERVER_DIR/server.js"
NODE_BIN="/data/data/com.termux/files/usr/bin/node"
PID_FILE="$SERVER_DIR/server.pid"
LOG_FILE="$SERVER_DIR/server.log"
ENDPOINTS_FILE="$SERVER_DIR/endpoints.txt"
PORT=3000

is_running() {
    if [ -f "$PID_FILE" ]; then
        local pid
        pid=$(cat "$PID_FILE" 2>/dev/null)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
    fi
    if pgrep -f "node.*(phone-mcp-server|PyPhone-MCP-Server)/server.js" >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

print_endpoints() {
    local port="${PORT:-3000}"
    local content=""
    content+="  - 端口: $port\n"
    content+="  - 本地端点: http://127.0.0.1:$port/mcp\n"
    local found_lan=0
    while IFS='=' read -r iface ip; do
        [ -z "$ip" ] && continue
        local label="网络 ($iface)"
        [[ "$iface" =~ ^wlan ]] && label="Wi-Fi ($iface)"
        [[ "$iface" =~ ^tun ]] && label="VPN ($iface)"
        content+="  - $label: http://$ip:$port/mcp\n"
        found_lan=1
    done < <(ifconfig 2>/dev/null | awk '
        /^[a-zA-Z0-9_-]+/ { iface=$1; sub(/:$/, "", iface) }
        /inet / {
            ip=$2
            if (ip != "127.0.0.1") {
                print iface "=" ip
            }
        }
    ')
    if [ "$found_lan" -eq 0 ]; then
        content+="  - 局域网: 未检测到 Wi-Fi / 网络连接\n"
    fi
    printf "%b" "$content" > "$ENDPOINTS_FILE"
    printf "%b" "$content"
}

start() {
    if is_running; then
        local pid
        pid=$(cat "$PID_FILE" 2>/dev/null || pgrep -f "node.*(phone-mcp-server|PyPhone-MCP-Server)/server.js" | head -n 1)
        echo "[phone-mcp] 服务已在运行 (PID: $pid)"
        print_endpoints
        return 0
    fi
    echo "[phone-mcp] 正在启动服务..."
    daemonize -a -c "$SERVER_DIR" -o "$LOG_FILE" -e "$LOG_FILE" -p "$PID_FILE" "$NODE_BIN" "$SERVER_JS"
    sleep 0.8
    if is_running; then
        local pid
        pid=$(cat "$PID_FILE" 2>/dev/null)
        echo "[phone-mcp] 服务启动成功 (PID: $pid)"
        print_endpoints
    else
        echo "[phone-mcp] 启动失败，请查看日志: $LOG_FILE"
        return 1
    fi
}

stop() {
    if ! is_running; then
        echo "[phone-mcp] 服务未运行"
        rm -f "$PID_FILE" "$ENDPOINTS_FILE" 2>/dev/null
        return 0
    fi
    echo "[phone-mcp] 正在停止服务..."
    if [ -f "$PID_FILE" ]; then
        local pid
        pid=$(cat "$PID_FILE" 2>/dev/null)
        if [ -n "$pid" ]; then
            kill "$pid" 2>/dev/null || true
        fi
        rm -f "$PID_FILE" 2>/dev/null
    fi
    pkill -f "node.*(phone-mcp-server|PyPhone-MCP-Server)/server.js" 2>/dev/null || true
    sleep 0.5
    if is_running; then
        pkill -9 -f "node.*(phone-mcp-server|PyPhone-MCP-Server)/server.js" 2>/dev/null || true
    fi
    rm -f "$ENDPOINTS_FILE" 2>/dev/null
    echo "[phone-mcp] 服务已停止"
}

restart() {
    stop
    sleep 0.5
    start
}

status() {
    if is_running; then
        local pid
        pid=$(cat "$PID_FILE" 2>/dev/null || pgrep -f "node.*(phone-mcp-server|PyPhone-MCP-Server)/server.js" | head -n 1)
        echo "[phone-mcp] 状态: 运行中 (PID: $pid)"
        print_endpoints
        local health
        health=$(curl -s --connect-timeout 2 "http://127.0.0.1:$PORT/health" 2>/dev/null)
        if [ -n "$health" ]; then
            echo "  - 健康状态: $health"
        fi
    else
        echo "[phone-mcp] 状态: 未运行"
    fi
}

logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -n "${1:-30}" -f "$LOG_FILE"
    else
        echo "[phone-mcp] 暂无日志文件: $LOG_FILE"
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
    endpoints|ip)
        print_endpoints
        ;;
    log|logs)
        logs "${2:-30}"
        ;;
    *)
        echo "用法: phone-mcp {start|stop|restart|status|endpoints|logs}"
        exit 1
        ;;
esac
