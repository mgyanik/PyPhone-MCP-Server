# PyPhone-MCP-Server

[中文](#中文说明) | [English](#english)

---

<a name="中文说明"></a>
## 中文说明

PyPhone-MCP-Server 是专为 Android / Termux 环境构建的轻量级、高性能 Model Context Protocol (MCP) HTTP 服务端。项目基于 Python 3 标准库实现，实现零外部运行时依赖，使各类 AI 客户端能够安全、可控地调度 Termux 本地开发环境与系统工具。

### 核心特性

- **零外部运行时依赖**：基于 Python 3 标准库构建，无需安装 pip 依赖包。
- **MCP Streamable HTTP 协议**：遵循 MCP 2024-11-05 规范，采用 SSE 长连接机制，支持跨会话状态自愈与心跳维持。
- **独立 WebUI 命令审批**：高危或未知 Shell 指令需通过内置 WebUI（端口 8080）显式批准，支持前缀通配与精确白/黑名单机制。
- **多层安全沙箱保护**：
  - 路径严格限制在 Termux 沙箱（`/data/data/com.termux/files/home`）内，阻断 `..` 相对越界与非法绝对路径访问。
  - 远程写操作（如 Git Push）基于参数特征 SHA-256 哈希生成一次性 Token，防范越权与重放攻击。
- **专职工程工具集**：提供结构化文件修改（行范围/全量覆写/代码大纲）、代码全文搜索、免 root 进程/端口探查及 GitHub 操作工具。

### 运行环境

- Android 设备（搭载 Termux 环境）
- Python 3.10 或更高版本：`pkg install python`
- Git：`pkg install git`

### 快速开始

#### 1. 克隆与目录就绪

```bash
git clone https://github.com/mgyanik/PyPhone-MCP-Server.git
cd PyPhone-MCP-Server
```

#### 2. 服务管理

使用内置脚本管理 MCP 主服务与 WebUI 进程：

```bash
chmod +x py-mcp.sh

# 启动服务
./py-mcp.sh start

# 查看运行状态与端点
./py-mcp.sh status

# 停止服务
./py-mcp.sh stop

# 重启服务
./py-mcp.sh restart
```

默认端点：
- MCP 接口服务：`http://<手机IP>:3000/mcp`
- 审批台 WebUI：`http://<手机IP>:8080`

### 客户端接入配置

以 Claude Desktop 或兼容客户端为例，在配置文件（如 `claude_desktop_config.json`）中添加：

```json
{
  "mcpServers": {
    "phone": {
      "url": "http://<手机IP>:3000/mcp"
    }
  }
}
```

### 工具清单

| 工具名称 | 功能描述 |
| :--- | :--- |
| `read_file_or_outline` | 读取文件文本、代码大纲或指定行号区间内容 |
| `patch_file` | 支持行号范围替换、符号替换、搜索替换及新建覆盖 |
| `list_directory` | 并发遍历目录结构并返回文件元数据 |
| `search_codebase` | 高性能代码检索，自动跳过版本控制与缓存目录 |
| `move_or_delete_file` | 安全移动、复制或移除受控沙箱内的文件与目录 |
| `inspect_file_meta` | 查看文件大小、权限模式、最后修改时间及 SHA-256 哈希 |
| `request_tool` | 统一系统命令执行网关，支持受控管道模式并接入 WebUI 审批 |
| `find_process` | 免 root 解析 `/proc` 表，探查本地监听端口与对应进程 |
| `take_github` | 统一 Git / GitHub CLI 接口，集成读写分级与 Token 鉴权 |
| `fetch_url` | 标准库 HTTP/HTTPS 请求调用工具 |
| `ask_user` | 远程高危写操作前置授权申请工具 |

### 许可证

MIT License. 详见 [LICENSE](LICENSE) 文件。

---

<a name="english"></a>
## English

PyPhone-MCP-Server is a lightweight, high-performance Model Context Protocol (MCP) HTTP server engineered specifically for Android / Termux environments. Built entirely on the Python 3 standard library with zero external dependencies, it allows AI clients to safely interface with Termux development toolchains.

### Features

- **Zero External Dependencies**: Implemented purely using Python 3 standard library modules.
- **MCP Streamable HTTP Transport**: Compliant with the MCP 2024-11-05 specification with Server-Sent Events (SSE) and session auto-recovery.
- **Independent WebUI Authorization**: Commands require approval via the embedded WebUI (port 8080), featuring whitelist and blacklist policies.
- **Multi-layer Security Sandbox**:
  - Confined strictly to the Termux root path (`/data/data/com.termux/files/home`), blocking relative path traversal (`..`) and absolute path escape.
  - Remote write operations (e.g., Git Push) require one-time SHA-256 parameter-bound authorization tokens.
- **Comprehensive Toolset**: Includes range-based file editors, codebase search, rootless process discovery, and controlled GitHub operations.

### Prerequisites

- Android device with Termux installed
- Python 3.10+: `pkg install python`
- Git: `pkg install git`

### Quick Start

#### 1. Clone Repository

```bash
git clone https://github.com/mgyanik/PyPhone-MCP-Server.git
cd PyPhone-MCP-Server
```

#### 2. Process Management

Manage background daemons using the control script:

```bash
chmod +x py-mcp.sh

# Start services
./py-mcp.sh start

# Check service status
./py-mcp.sh status

# Stop services
./py-mcp.sh stop

# Restart services
./py-mcp.sh restart
```

Endpoints:
- MCP Server: `http://<PHONE_IP>:3000/mcp`
- WebUI Console: `http://<PHONE_IP>:8080`

### Client Configuration

Add the server to your MCP client configuration (e.g., `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "phone": {
      "url": "http://<PHONE_IP>:3000/mcp"
    }
  }
}
```

### License

MIT License. See [LICENSE](LICENSE) for details.
