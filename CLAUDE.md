# 项目约定 — PyPhone-MCP-Server

本文件是 Agent 维护本项目时必须遵守的规范。改动代码必须保证 `make check` 全量通过。

## 1. 项目定位与核心指标

专为 Android / Termux 环境打造的轻量、高性能 MCP (Model Context Protocol) Streamable HTTP 服务端（面向 Kelivo 等客户端）。

- **零外部运行时依赖**：基于 Python 标准库实现高并发与流式通信。
- **高吞吐低延迟**：全局常驻工作线程池管理 IO 与计算，避免临时创建线程的损耗。
- **紧凑输出**：纯净结构化数据返回，极致节省 Token。

## 2. 目录架构

```
src/
  config.py                 # 全局运行配置与 Termux 环境变量
  server.py                 # HTTP/SSE 传输层入口
  registry.py               # MCP 工具注册中心与 Schema 生成
  core/                     # 核心协议与基础设施
    protocol.py             # JSON-RPC 2.0 协议规范
    session.py              # 客户端会话管理与断线恢复
    pool.py                 # 全局常驻高并发工作线程池
    policy.py               # 命令安全策略审查引擎 (ALLOW / ASK / DENY)
    task_store.py           # 异步长任务生命周期与进程调度
    logging.py              # 结构化日志
  tools/                    # 工具实现层 (一文件一工具)
    read_file.py            # read_file (单文件或并发批量读取)
    read_file_lines.py      # read_file_lines (分页按行读取大文件局部窗口)
    edit_file.py            # edit_file (按行号范围精准替换/插入、全量覆写或新建)
    manage_file.py          # manage_file (安全移动/复制/删除文件与目录)
    get_file_info.py        # get_file_info (文件元数据与SHA-256校验)
    list_dir.py             # list_dir (并发目录浏览)
    search_text.py          # search_text (并发关键词流式检索)
    run_command.py          # run_command (同步执行短命令，5s 硬超时)
    run_background_command.py # run_background_command (异步派发长任务 > 5s)
    get_task_status.py      # get_task_status (长任务状态与日志查询)
    list_tasks.py           # list_tasks (已派发任务列表)
    cancel_task.py          # cancel_task (终止长任务)
    fetch_url.py            # fetch_url (纯标准库 HTTP/HTTPS 请求)
    find_process.py         # find_process (按端口或名称排查进程)
    kill_process.py         # kill_process (根据 PID 安全终止进程)
    get_device_status.py    # get_device_status (存储/内存/CPU/电量状态)
tests/                      # 自动化测试用例集
Makefile                    # make check 一键回归
pyproject.toml              # 现代 Python 项目元数据
py-mcp.sh                   # 守护进程管理脚本 (start/stop/restart/status/logs)
```

## 3. 工具矩阵

| 工具名 | 注解 (Annotations) | 适用场景与关键指引 |
|---|---|---|
| `read_file` | `readOnlyHint` | 批量或单个读取文件内容（优先数组传入并发读取）；大文件请用 `read_file_lines`（兼容 `read_files` 别名） |
| `read_file_lines` | `readOnlyHint` | 1-based 按行分页读取大文件局部窗口（指定 start_line 与 line_count），大幅节省 Token |
| `edit_file` | `destructiveHint` | 高效行号区间替换（指定 start_line/end_line 与 new_text，极省 Token 免传旧代码）、全量覆写或新建 |
| `manage_file` | `destructiveHint` | 安全移动、复制、删除文件与目录（替代 `mv`/`cp`/`rm`，内置系统根目录防误删） |
| `get_file_info` | `readOnlyHint` | 查看文件/目录是否存在、大小、修改时间、权限，按需计算 SHA-256 哈希（兼容 `file_info` 别名） |
| `list_dir` | `readOnlyHint` | 批量或单个列出目录项（目录在前、文件在后，带大小） |
| `search_text` | `readOnlyHint` | 关键词流式搜索（自动剪枝忽略编译/缓存目录，跳过 >5MB 大文件，兼容 `search_texts` 别名） |
| `fetch_url` | `destructiveHint: False` | 纯 Python 标准库发送 HTTP/HTTPS 请求（彻底杜绝 shell curl 引号/转义灾难） |
| `find_process` | `readOnlyHint` | 根据监听网络端口 (port) 或进程名关键词 (name) 排查进程，免用 `lsof`/`netstat` |
| `kill_process` | `destructiveHint` | 根据 PID 优雅或强制终止进程（严禁误杀 MCP 自身和系统 1 号进程） |
| `get_device_status` | `readOnlyHint` | 查询手机存储空间、可用内存 (RAM)、CPU 负载与电池电量/充电状态 |
| `run_command` | `destructiveHint` | **⚠️ 仅供用于专用工具做不到的时候使用**。前台同步执行命令，默认 5 秒硬超时 |
| `run_background_command` | `destructiveHint` | 异步派发后台长任务（预估耗时 > 5s，如编译、下载、服务），立即返回 task_id |
| `get_task_status` | `readOnlyHint` | 轮询查询后台长任务执行状态、退出码与终端输出 |
| `list_tasks` | `readOnlyHint` | 列出后台所有已派发任务（支持状态过滤） |
| `cancel_task` | `destructiveHint` | 终止进行中的后台长任务（SIGTERM -> 等待 -> SIGKILL） |

## 4. 核心安全策略 (Policy)

命令执行统一经过 `policy.evaluate()`：
- **ALLOW**：安全只读白名单命令，直接执行。
- **ASK**：敏感或未知命令，服务端放行执行并在后台记录结构化审计日志（由客户端把关审批）。
- **DENY**：高危禁止命令（破坏系统等高危操作），绝对阻断拒绝。

## 5. 任务分级执行原则与工具选择

- **优先使用专用工具**：
  - 读文件用 `read_file` 或 `read_file_lines`
  - 改/写文件用 `edit_file`（强烈推荐 `start_line` / `end_line` 方式）
  - 移动/复制/删文件用 `manage_file`
  - 查文件属性/校验哈希用 `get_file_info`
  - 浏览目录用 `list_dir`
  - 搜索文本用 `search_text`
  - 网络请求用 `fetch_url`
  - 查杀进程用 `find_process` / `kill_process`
  - 查设备状态用 `get_device_status`
- **`run_command` 严格受限**：**⚠️ 仅供用于专用工具做不到的时候使用**，默认硬超时为 **5 秒**。
- **耗时任务（> 5 秒）**：如构建、编译、批量测试、后台服务，必须使用 `run_background_command` 派发。
- **批量处理**：支持批量的只读工具必须优先使用数组传入，充分发挥 `core/pool` 并发能力。

## 6. 开发与测试

新增或修改代码后必须运行回归测试：
```bash
make check
```
必须保证测试全部通过方可提交或上线。
