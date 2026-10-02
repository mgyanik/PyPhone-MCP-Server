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
    read_file.py            # read_files
    edit_file.py            # edit_file
    list_dir.py             # list_dir
    search_text.py          # search_texts
    run_command.py          # run_command
    run_background_command.py # run_background_command
    get_task_status.py      # get_task_status
    list_tasks.py           # list_tasks
    cancel_task.py          # cancel_task
tests/                      # 自动化测试用例集
Makefile                    # make check 一键回归
pyproject.toml              # 现代 Python 项目元数据
py-mcp.sh                   # 守护进程管理脚本 (start/stop/restart/status/logs)
```

## 3. 工具矩阵

| 工具名 | 注解 (Annotations) | 适用场景 |
|---|---|---|
| `read_files` | `readOnlyHint` | 批量或单个读取文件内容（并发 IO） |
| `edit_file` | `destructiveHint` | 文件精准唯一字符串替换、全量覆写或新建（原子安全写入） |
| `list_dir` | `readOnlyHint` | 批量或单个列出目录项（目录在前、文件在后） |
| `search_texts` | `readOnlyHint` | 批量关键词流式搜索（自动剪枝忽略编译/缓存目录） |
| `run_command` | `destructiveHint` | 实时前台同步执行命令（预估耗时 <= 8s），带超时与截断保护 |
| `run_background_command` | `destructiveHint` | 异步派发后台长任务（预估耗时 > 8s），立即返回 task_id |
| `get_task_status` | `readOnlyHint` | 查询后台任务执行状态与终端输出 |
| `list_tasks` | `readOnlyHint` | 列出后台所有已派发任务 |
| `cancel_task` | `destructiveHint` | 终止进行中的后台长任务 |

## 4. 核心安全策略 (Policy)

命令执行统一经过 `policy.evaluate()`：
- **ALLOW**：安全只读白名单命令，直接执行。
- **ASK**：敏感或未知命令，服务端放行执行并在后台记录结构化审计日志（由客户端把关审批）。
- **DENY**：高危禁止命令（破坏系统等高危操作），绝对阻断拒绝。

## 5. 任务分级执行原则

- **短任务（<= 8 秒）**：使用 `run_command`，同步等待返回。
- **耗时任务（> 8 秒）**：如构建、编译、批量测试、后台服务，必须使用 `run_background_command` 派发。
- **批量处理**：支持批量的只读工具必须优先使用数组传入，充分发挥 `core/pool` 并发能力。

## 6. 开发与测试

新增或修改代码后必须运行回归测试：
```bash
make check
```
必须保证测试全部通过方可提交或上线。
