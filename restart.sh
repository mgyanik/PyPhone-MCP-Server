#!/data/data/com.termux/files/usr/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
echo "Stopping old server..."
pkill -f "node.*/phone-mcp-server/server.js"
sleep 0.5
echo "Starting new server..."
cd "$DIR"
nohup node server.js >> server.log 2>&1 &
sleep 0.5
if pgrep -f "node.*/phone-mcp-server/server.js" >/dev/null; then
    echo "phone-mcp-server successfully restarted!"
else
    echo "Failed to start phone-mcp-server. Check server.log for details."
fi
