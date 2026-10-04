import os
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from src.core.auth_store import PENDING_FILE, WHITELIST_FILE, BLACKLIST_FILE, LOG_FILE, _read_json, _atomic_write

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>MCP 安全沙箱</title>
    <style>
        :root { --bg: #f3f4f6; --card: #ffffff; --text: #1f2937; --gray: #6b7280; --primary: #3b82f6; --success: #10b981; --danger: #ef4444; --border: #e5e7eb; }
        @media (prefers-color-scheme: dark) { :root { --bg: #111827; --card: #1f2937; --text: #f9fafb; --gray: #9ca3af; --border: #374151; } }
        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
        body { font-family: system-ui, -apple-system, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 12px; line-height: 1.5; font-size: 16px; }
        
        .header { display: flex; justify-content: space-between; align-items: center; padding-bottom: 12px; margin-bottom: 12px; border-bottom: 1px solid var(--border); }
        .header h2 { margin: 0; font-size: 20px; font-weight: 600; display: flex; align-items: center; gap: 8px; }
        .sync-time { font-size: 12px; color: var(--gray); }
        
        .nav { display: flex; gap: 8px; margin-bottom: 16px; overflow-x: auto; padding-bottom: 4px; scrollbar-width: none; }
        .nav::-webkit-scrollbar { display: none; }
        .nav button { flex: 0 0 auto; background: var(--card); border: 1px solid var(--border); color: var(--gray); font-size: 15px; cursor: pointer; padding: 10px 16px; border-radius: 20px; font-weight: 500; transition: 0.2s; white-space: nowrap; }
        .nav button.active { background: var(--primary); color: white; border-color: var(--primary); }
        
        .card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 16px; margin-bottom: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
        
        .badge { display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; margin-bottom: 8px; }
        .badge.exact { background: #e0e7ff; color: #4338ca; border: 1px solid #c7d2fe; } 
        .badge.prefix { background: #dcfce3; color: #166534; border: 1px solid #bbf7d0; }
        .badge.pending { background: #fef9c3; color: #854d0e; border: 1px solid #fef08a; }
        .badge.danger { background: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
        
        .code { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; background: rgba(128,128,128,0.1); padding: 8px 12px; border-radius: 8px; font-size: 14px; word-break: break-all; display: block; margin: 8px 0; border: 1px solid var(--border); }
        
        .meta-text { font-size: 13px; color: var(--gray); margin-bottom: 4px; }
        .meta-text strong { color: var(--text); font-weight: 500; }
        
        .controls { display: flex; flex-direction: column; gap: 10px; margin-top: 16px; border-top: 1px dashed var(--border); padding-top: 16px; }
        select { width: 100%; padding: 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--bg); color: var(--text); font-size: 15px; outline: none; appearance: none; }
        .btn-group { display: flex; gap: 10px; }
        button.action-btn { flex: 1; padding: 12px; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; border: none; color: white; display: flex; justify-content: center; align-items: center; gap: 6px; }
        .btn-success { background: var(--success); }
        .btn-danger { background: var(--danger); }
        .btn-outline { background: transparent; border: 1px solid var(--danger) !important; color: var(--danger) !important; }
        
        .empty-state { text-align: center; color: var(--gray); padding: 40px 20px; font-size: 15px; }
        .hidden { display: none; }
    </style>
</head>
<body>
    <div class="header">
        <h2>🛡️ MCP 审批台</h2>
        <span class="sync-time" id="last-sync">--:--</span>
    </div>

    <div class="nav">
        <button id="tab-pending" class="active" onclick="switchTab('pending')">待审批 <span id="badge-pending"></span></button>
        <button id="tab-whitelist" onclick="switchTab('whitelist')">白名单</button>
        <button id="tab-blacklist" onclick="switchTab('blacklist')">黑名单</button>
        <button id="tab-logs" onclick="switchTab('logs')">日志</button>
    </div>

    <div id="view-pending"></div>
    <div id="view-whitelist" class="hidden"></div>
    <div id="view-blacklist" class="hidden"></div>
    <div id="view-logs" class="hidden"></div>

    <script>
        let currentData = { pending: [], whitelist: [], blacklist: [], logs: [] };

        function switchTab(tab) {
            ['pending', 'whitelist', 'blacklist', 'logs'].forEach(t => {
                document.getElementById('view-' + t).classList.add('hidden');
                document.getElementById('tab-' + t).classList.remove('active');
            });
            document.getElementById('view-' + tab).classList.remove('hidden');
            document.getElementById('tab-' + tab).classList.add('active');
            render();
        }

        async function fetchData() {
            try {
                const res = await fetch('/api/data');
                currentData = await res.json();
                const d = new Date();
                document.getElementById('last-sync').innerText = `${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}:${d.getSeconds().toString().padStart(2,'0')}`;
                document.getElementById('badge-pending').innerText = currentData.pending.length > 0 ? `(${currentData.pending.length})` : '';
                render();
            } catch (e) { console.error("Fetch error:", e); }
        }

        async function postAction(url, payload) {
            try {
                await fetch(url, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
                fetchData();
            } catch(e) { alert("操作失败: " + e); }
        }

        function buildTokens(command, mode) {
            if (mode === 'exact') return command;
            if (mode === 'prefix_1') return command.slice(0, 1);
            if (mode === 'prefix_2') return command.slice(0, 2);
            return command;
        }

        function handleProcess(reqId, isApprove) {
            const req = currentData.pending.find(p => p.request_id === reqId);
            const mode = document.getElementById('mode-' + reqId).value;
            const tokens = buildTokens(req.command, mode);
            const payload = { request_id: reqId, tokens: tokens, match: mode === 'exact' ? 'exact' : 'prefix' };
            postAction(isApprove ? '/api/approve' : '/api/reject', payload);
        }

        function deleteRule(list, index) {
            if (confirm("确定要删除这条规则吗？")) postAction('/api/delete_rule', { list: list, index: index });
        }

        function render() {
            // Pending Render
            const pDiv = document.getElementById('view-pending');
            if (currentData.pending.length === 0) {
                pDiv.innerHTML = '<div class="empty-state">🎉 目前没有需要您审批的请求</div>';
            } else {
                pDiv.innerHTML = currentData.pending.map(p => `
                    <div class="card">
                        <span class="badge pending">待审批</span>
                        <div class="code">${p.command.join(' ')}</div>
                        <div class="meta-text"><strong>工作目录:</strong> ${p.cwd}</div>
                        <div class="meta-text"><strong>申请原因:</strong> ${p.reason}</div>
                        
                        <div class="controls">
                            <select id="mode-${p.request_id}">
                                <option value="exact">🎯 精确匹配 (仅允许此完整命令)</option>
                                <option value="prefix_1">📁 母命令通配 (允许 ${p.command[0]} 的所有参数)</option>
                                ${p.command.length > 1 ? `<option value="prefix_2">📄 子命令通配 (允许 ${p.command[0]} ${p.command[1]} 的参数)</option>` : ''}
                            </select>
                            <div class="btn-group">
                                <button class="action-btn btn-success" onclick="handleProcess('${p.request_id}', true)">✅ 批准</button>
                                <button class="action-btn btn-danger" onclick="handleProcess('${p.request_id}', false)">🚫 拉黑</button>
                            </div>
                        </div>
                    </div>
                `).join('');
            }

            // Rules Render
            const renderRules = (entries, id, type) => {
                const div = document.getElementById(id);
                if (!entries || entries.length === 0) {
                    div.innerHTML = `<div class="empty-state">暂无规则记录</div>`;
                    return;
                }
                div.innerHTML = entries.map((r, i) => `
                    <div class="card">
                        <div class="card-header">
                            <span class="badge ${r.match}">${r.match === 'exact' ? '🎯 精确匹配' : '📁 前缀通配'}</span>
                            <button class="action-btn btn-outline" style="padding: 4px 12px; font-size: 13px; width: auto;" onclick="deleteRule('${type}', ${i})">删除</button>
                        </div>
                        <div class="code" style="margin-top:0;">${r.tokens.join(' ')} ${r.match === 'prefix' ? '...' : ''}</div>
                        <div class="meta-text" style="font-size: 12px;">时间: ${r.approved_at || r.blocked_at || '未知'}</div>
                    </div>
                `).join('');
            };
            renderRules(currentData.whitelist, 'view-whitelist', 'whitelist');
            renderRules(currentData.blacklist, 'view-blacklist', 'blacklist');
            
            // Logs Render
            const lDiv = document.getElementById('view-logs');
            if (!currentData.logs || currentData.logs.length === 0) {
                lDiv.innerHTML = `<div class="empty-state">暂无执行日志</div>`;
            } else {
                lDiv.innerHTML = currentData.logs.slice().reverse().map(l => `
                    <div class="card">
                        <div class="card-header" style="margin-bottom: 4px;">
                            <span class="badge ${l.result === 'success' ? 'prefix' : 'danger'}">${l.result === 'success' ? '✅ 成功' : '❌ 失败'}</span>
                            <span style="font-size: 12px; color: var(--gray);">${l.timestamp.substring(11, 16)}</span>
                        </div>
                        <div class="code" style="margin-top:0; margin-bottom: 8px; font-size: 13px;">${l.command.join(' ')}</div>
                        <div class="meta-text" style="font-size: 12px;">退出码: ${l.exit_code} | 命中规则: ${l.rule ? l.rule.match : '无'}</div>
                    </div>
                `).join('');
            }
        }

        setInterval(fetchData, 2000);
        fetchData();
    </script>
</body>
</html>"""

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML.encode('utf-8'))
        elif self.path == '/api/data':
            wl = _read_json(WHITELIST_FILE, {"entries": []})
            bl = _read_json(BLACKLIST_FILE, {"entries": []})
            pend = _read_json(PENDING_FILE, [])
            logs = []
            if os.path.exists(LOG_FILE):
                try:
                    with open(LOG_FILE, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                        logs = [json.loads(l) for l in lines[-50:] if l.strip()]
                except Exception:
                    pass
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"pending": pend, "whitelist": wl.get("entries", []), "blacklist": bl.get("entries", []), "logs": logs}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(length))
            
            if self.path in ['/api/approve', '/api/reject']:
                req_id = data.get("request_id")
                
                pend = _read_json(PENDING_FILE, [])
                pend = [p for p in pend if p.get("request_id") != req_id]
                _atomic_write(PENDING_FILE, pend)
                
                is_appr = (self.path == '/api/approve')
                t_file = WHITELIST_FILE if is_appr else BLACKLIST_FILE
                rules = _read_json(t_file, {"entries": []})
                
                rule = {"tokens": data.get("tokens"), "match": data.get("match")}
                if is_appr: rule["approved_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                else: rule["blocked_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()); rule["reason"] = "user_rejected"
                    
                rules.setdefault("entries", []).append(rule)
                _atomic_write(t_file, rules)
                
            elif self.path == '/api/delete_rule':
                t_file = WHITELIST_FILE if data.get("list") == "whitelist" else BLACKLIST_FILE
                rules = _read_json(t_file, {"entries": []})
                idx = int(data.get("index"))
                if 0 <= idx < len(rules.get("entries", [])):
                    rules["entries"].pop(idx)
                    _atomic_write(t_file, rules)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode('utf-8'))
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode('utf-8'))

    def log_message(self, format, *args): pass

def run_server(port=8080):
    server = ThreadingHTTPServer(('0.0.0.0', port), RequestHandler)
    server.serve_forever()

if __name__ == '__main__':
    run_server()
