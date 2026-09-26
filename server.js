#!/usr/bin/env node

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import express from "express";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { randomUUID } from "node:crypto";
import os from "node:os";
import fs from "node:fs";
import { z } from "zod";

const exec = promisify(execFile);

const args = process.argv.slice(2);
const VERBOSE = args.includes("--verbose") || args.includes("-v");
const PORT =
  parseInt(args.find((_, i, a) => a[i - 1] === "--port") ?? "") ||
  parseInt(process.env.PORT ?? "") ||
  3000;

const TERMUX_PREFIX = "/data/data/com.termux/files/usr";
const TERMUX_HOME = "/data/data/com.termux/files/home";

// 注入完整 Termux 环境
const DEFAULT_ENV = {
  ...process.env,
  HOME: TERMUX_HOME,
  PREFIX: TERMUX_PREFIX,
  PATH: `${TERMUX_PREFIX}/bin:${TERMUX_PREFIX}/bin/applets:${process.env.PATH || ""}:/system/bin:/system/xbin`,
  TMPDIR: `${TERMUX_PREFIX}/tmp`,
  LANG: "C.UTF-8",
  TERM: "xterm-256color",
};

// 优先使用 Termux 的 Bash
const SHELL_BIN = fs.existsSync(`${TERMUX_PREFIX}/bin/bash`)
  ? `${TERMUX_PREFIX}/bin/bash`
  : (fs.existsSync(`${TERMUX_PREFIX}/bin/sh`) ? `${TERMUX_PREFIX}/bin/sh` : "/system/bin/sh");

// 默认单次命令超时 60s
const DEFAULT_TIMEOUT_MS = parseInt(process.env.EXEC_TIMEOUT ?? "60000", 10);
// 结果最大保留字符数（避免撑爆上下文）
const MAX_OUTPUT_CHARS = 45000;

function log(...msg) {
  console.log('[phone-mcp]', ...msg);
}

function debug(...msg) {
  if (VERBOSE) console.log('[phone-mcp:debug]', ...msg);
}

function formatElapsed(start) {
  const ms = Math.round(performance.now() - start);
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(2)}s`;
}

function truncateOutput(str) {
  if (!str || str.length <= MAX_OUTPUT_CHARS) return str;
  const head = str.slice(0, 30000);
  const tail = str.slice(-15000);
  const omitted = str.length - 45000;
  return `${head}\n\n... [输出过长 (总计 ${str.length} 字符)，已折叠中间约 ${omitted} 字符] ...\n\n${tail}`;
}

function text(content) {
  return {
    content: [
      {
        type: "text",
        text: typeof content === "string" ? content : JSON.stringify(content),
      },
    ],
  };
}

function err(message) {
  return {
    content: [{ type: "text", text: 'Error: ' + message }],
    isError: true,
  };
}

function createMcpServer() {
  const server = new McpServer({
    name: "phone-mcp",
    version: "1.0.0",
  });

  server.tool(
    "shell",
    {
      command: z.string().describe("The shell command to execute"),
      timeout: z.number().optional().describe("Execution timeout in milliseconds (default: 60000)"),
    },
    async ({ command, timeout }) => {
      const start = performance.now();
      const timeoutMs = timeout && timeout > 0 ? timeout : DEFAULT_TIMEOUT_MS;
      const cmdPreview = command.length > 80 ? command.slice(0, 77) + "..." : command;

      try {
        const { stdout, stderr } = await exec(SHELL_BIN, ["-c", command], {
          timeout: timeoutMs,
          maxBuffer: 10 * 1024 * 1024, // 10MB
          env: DEFAULT_ENV,
          cwd: TERMUX_HOME,
        });

        const elapsed = formatElapsed(start);
        log(`[EXEC ${elapsed}] ${cmdPreview}`);

        let output = [stdout.trim(), stderr.trim()].filter(Boolean).join("\n---stderr---\n");
        output = truncateOutput(output || "(no output)");
        return text(output + "\n\n[耗时: " + elapsed + "]");
      } catch (e) {
        const elapsed = formatElapsed(start);
        log(`[ERR ${elapsed}] ${cmdPreview}`);

        let out = "";
        if (e.killed || e.signal === "SIGTERM" || e.code === "ETIMEDOUT") {
          out = `命令执行超时 (限制: ${timeoutMs / 1000}s)`;
        } else {
          out = [e.stdout?.trim(), e.stderr?.trim()].filter(Boolean).join("\n---stderr---\n") || e.message;
        }

        out = truncateOutput(out);
        return err(out + "\n\n[耗时: " + elapsed + "]");
      }
    }
  );

  return server;
}

const app = express();
app.disable("x-powered-by");
app.use(express.json({ limit: '500mb' }));
app.use(express.urlencoded({ limit: '500mb', extended: true }));

const transports = new Map();

app.get("/health", (_req, res) => {
  res.json({
    status: "ok",
    server: "phone-mcp",
    version: "1.0.0",
    uptime: process.uptime(),
    tools: 1,
    shell: SHELL_BIN,
  });
});

app.post("/mcp", async (req, res) => {
  try {
    const sessionId = req.headers["mcp-session-id"];
    let sessionData;

    if (sessionId) {
      sessionData = transports.get(sessionId);
      if (!sessionData) {
        res.status(404).json({ error: "Session not found or expired" });
        return;
      }
    } else {
      const server = createMcpServer();
      let currentSessionId = null;

      const transport = new StreamableHTTPServerTransport({
        sessionIdGenerator: () => randomUUID(),
        onsessioninitialized: (id) => {
          currentSessionId = id;
          transports.set(id, { transport, server });
          debug('Session initialized: ' + id);
        },
      });

      transport.onclose = () => {
        if (currentSessionId) {
          transports.delete(currentSessionId);
          server.close().catch(() => {});
          debug('Session closed: ' + currentSessionId);
        }
      };

      await server.connect(transport);
      sessionData = { transport, server };
    }

    await sessionData.transport.handleRequest(req, res, req.body);
  } catch (e) {
    log("Error handling POST /mcp:", e.message);
    if (!res.headersSent) {
      res.status(500).json({ error: e.message });
    }
  }
});

app.get("/mcp", async (req, res) => {
  const sessionId = req.headers["mcp-session-id"];
  if (!sessionId || !transports.has(sessionId)) {
    res.status(404).json({ error: "Missing or invalid session ID" });
    return;
  }
  const { transport } = transports.get(sessionId);
  await transport.handleRequest(req, res);
});

app.delete("/mcp", async (req, res) => {
  const sessionId = req.headers["mcp-session-id"];
  if (sessionId && transports.has(sessionId)) {
    const { transport, server } = transports.get(sessionId);
    await transport.handleRequest(req, res);
    transports.delete(sessionId);
    server.close().catch(() => {});
  } else {
    res.status(404).json({ error: "Session not found" });
  }
});

function getLocalIP() {
  const interfaces = os.networkInterfaces();
  for (const name of Object.keys(interfaces)) {
    for (const iface of interfaces[name]) {
      if (iface.family === "IPv4" && !iface.internal) {
        return iface.address;
      }
    }
  }
  return "127.0.0.1";
}

app.listen(PORT, "0.0.0.0", () => {
  const ip = getLocalIP();
  log("========================================");
  log(" phone-mcp-server is running!");
  log('   Local:   http://localhost:' + PORT + '/mcp');
  log('   Network: http://' + ip + ':' + PORT + '/mcp');
  log('   Health:  http://' + ip + ':' + PORT + '/health');
  log("   Tools:   1 tool (shell)");
  log("   Shell:   " + SHELL_BIN);
  log("========================================");
});

function cleanup() {
  log("Stopping server...");
  for (const [id, { transport, server }] of transports.entries()) {
    transport.close?.().catch(() => {});
    server.close?.().catch(() => {});
  }
  transports.clear();
  process.exit(0);
}

process.on("SIGINT", cleanup);
process.on("SIGTERM", cleanup);
