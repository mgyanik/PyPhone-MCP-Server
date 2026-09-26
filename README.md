# 📱 phone-mcp-server

[English](#english) | [中文说明](#中文说明)

---

<a name="english"></a>
## English

> Turn your Android phone into an MCP server for AI assistants — powerful shell and device integration via Termux.

Built on the [Model Context Protocol (MCP)](https://modelcontextprotocol.io), this server allows AI assistants (like Claude Desktop, Cursor, GitHub Copilot CLI, etc.) to securely interact with your Android device running [Termux](https://termux.dev).

> [!NOTE]
> **Active Maintenance & Fixes**: This repository is actively maintained. Compared to the upstream project, known bugs have been addressed and optimized (including environment variables, session lifecycles, execution timeouts, and response truncation). If you encounter any issues or have feature requests, please feel free to **open an Issue** — they will be handled promptly!

### ✨ Features

- **Full Termux Environment**: Executes commands within Termux's native environment (`/data/data/com.termux/files/usr/bin`), retaining path resolution and shell behavior.
- **Robust Shell Tool**:
  - Configurable timeouts (default: 60s).
  - Smart output truncation (protecting client context from massive terminal dumps).
  - Detailed runtime execution profiling and exit-code reporting.
- **MCP Streamable HTTP Transport**: Modern HTTP transport supporting multi-session MCP clients.
- **Service Management**: Includes `restart.sh` helper script for easy background lifecycle management.

### 📋 Prerequisites

- **Android Phone**
- **[Termux](https://f-droid.org/en/packages/com.termux/)** installed from F-Droid
- **Node.js**: `pkg install nodejs-lts`

### 🚀 Quick Start

#### 1. Installation

```bash
git clone https://github.com/mgyanik/phone-mcp-server.git
cd phone-mcp-server
npm install
```

#### 2. Running the Server

Start in foreground:
```bash
node server.js
```

Or run in background / restart:
```bash
chmod +x restart.sh
./restart.sh
```

#### 3. MCP Client Configuration

Add to your MCP client config (e.g. `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "phone": {
      "url": "http://<PHONE_IP>:3000/mcp"
    }
  }
}
```

Replace `<PHONE_IP>` with your phone's Wi-Fi IP address (displayed in server console output).

---

<a name="中文说明"></a>
## 中文说明

> 将你的 Android 手机打造成面向 AI 助手的 MCP 服务端 —— 通过 Termux 提供强大的 Shell 与设备控制能力。

本项目基于 [Model Context Protocol (MCP)](https://modelcontextprotocol.io)，让 AI 编程助手（如 Claude Desktop、Cursor、GitHub Copilot CLI 等）能够直接与运行 [Termux](https://termux.dev) 的安卓设备无缝交互。

> [!NOTE]
> **长期维护与已知问题修复**：本项目为一个**长期活跃维护**的版本。相较原版，我们对已知的大多数缺陷与体验问题进行了针对性修改与重构（如 Termux 原生环境变量加载、会话生命周期回收、超时与大流量输出折叠等）。如果您在使用过程中遇到任何问题或有新功能需求，欢迎随时提交 **Issue**，我们会尽快响应和修复！

### ✨ 功能特点

- **原生 Termux 运行环境**：自动注入 Termux 环境变量与 `$PREFIX/bin` 路径，完整保留 Termux 终端生态与工具链支持。
- **增强型 Shell 工具**：
  - 支持可配置超时控制（默认 60 秒）。
  - 智能长输出折叠截断（避免命令输出过长刷屏撑爆 AI 上下文窗口）。
  - 精确记录并展示每条命令的耗时和执行状态。
- **MCP Streamable HTTP 协议**：基于官方标准 HTTP 传输协议，支持多客户端会话管理。
- **便捷启停脚本**：附带 `restart.sh`，支持一键热重载与后台静默运行。

### 📋 准备工作

- **安卓手机**（Android 设备）
- **[Termux](https://f-droid.org/en/packages/com.termux/)**（推荐从 F-Droid 下载安装）
- **Node.js 环境**：`pkg install nodejs-lts`

### 🚀 快速上手

#### 1. 安装项目

```bash
git clone https://github.com/mgyanik/phone-mcp-server.git
cd phone-mcp-server
npm install
```

#### 2. 启动服务

前台运行：
```bash
node server.js
```

或者使用重载脚本后台启动：
```bash
chmod +x restart.sh
./restart.sh
```

#### 3. 配置 MCP 客户端

在你的客户端配置（如 `claude_desktop_config.json`）中添加：

```json
{
  "mcpServers": {
    "phone": {
      "url": "http://<手机局域网IP>:3000/mcp"
    }
  }
}
```

将 `<手机局域网IP>` 替换为你手机当前的 Wi-Fi IP 地址（服务启动日志会打印具体地址）。

### 📄 License

MIT — see [LICENSE](LICENSE).
