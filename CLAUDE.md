# 项目约定 — PyPhone-MCP-Server

本文件是 agent 修改本项目时必须遵守的规范。改代码前先读完。
与本文件冲突的“通用最佳实践”，一律以本文件为准。

## 1. 项目定位

MCP Server，向 LLM 客户端（当前主要客户端：Kelivo）暴露语义化工具，
用于读取文件、编辑文件、搜索、执行命令与异步长任务管理。

四个核心目标：
1. 工具语义清晰，LLM 能准确选择
2. 风险分级明确，服务端为唯一防线
3. 日志结构化，人类可读可审计
4. 输出紧凑经济：使用英文、不输出冗余 summary 字段（极致节省 Token）

## 2. 双栈现状

- Node 版：历史遗留，已清理下线
- Python 版：`src/server.py`，默认监听 3000 端口，当前唯一主力服务端

## 3. 目录结构

```
src/
  server.py                 # MCP Streamable HTTP 服务入口，默认监听 3000
  registry.py               # 工具注册表与 schema 生成
  policy.py                 # 策略引擎（ALLOW / ASK / DENY）
  task_store.py             # 异步长任务存储与生命周期
  logging.py                # 结构化日志
  tools/                    # 一文件一工具
    read_file.py            # read_files（批量/单文件读取）
    edit_file.py            # edit_file（单文件精准文本替换与创建）
    list_dir.py             # list_dir（批量/单目录列举）
    search_text.py          # search_texts（批量关键词检索）
    run_command.py          # run_command（实时前台命令执行，同步等待返回）
    run_background_command.py # run_background_command（异步长任务派发）
    get_task_status.py      # 查询后台任务状态与输出
    list_tasks.py           # 列举后台任务
    cancel_task.py          # 取消后台任务
tests/
  test_annotations.py
  test_policy.py
  test_realtime_task.py
  test_tasks.py
  test_server.py
  test_edit_file.py
Makefile                    # make check 一键回归
CLAUDE.md                   # 本文件
```

新增工具只在 `src/tools/` 下新建文件，并在 `registry.load_tools()` 注册。

## 4. 工具命名与职责

| 工具名 | 权限与提示 | 用途说明 |
|---|---|---|
| `read_files` | `readOnlyHint` | 批量/单个读取文本文件内容 |
| `edit_file` | `destructiveHint` | 文件精准唯一字符串替换、全量覆写或创建 |
| `list_dir` | `readOnlyHint` | 批量/单个列出目录项（目录在前、文件在后） |
| `search_texts` | `readOnlyHint` | 批量关键词在工作区检索 |
| `run_command` | `destructiveHint` | 同步执行实时短命令（<=8s），超时与输出截断保护 |
| `run_background_command` | `destructiveHint` | 异步派发耗时命令（预计>8s），立即返回 task_id |
| `get_task_status` | `readOnlyHint` | 查询后台任务的状态（running/done/failed/canceled/denied）与输出 |
| `list_tasks` | `readOnlyHint` | 列出当前所有已注册的后台任务 |
| `cancel_task` | `destructiveHint` | 终止进行中的后台任务 |

## 5. Annotations

每个工具必须声明 annotations，`test_annotations.py` 会遍历检查。

- 只读工具：`annotations={"readOnlyHint": True}`
- 有副作用工具：`annotations={"destructiveHint": True}`

注意：Kelivo 当前版本不消费 annotations（仅存储）。
annotations 保留是为了符合 MCP 规范并兼容其他客户端。
不要因为“Kelivo 不读”而省略 annotations。

## 6. 策略引擎（安全核心）

### 唯一入口

所有命令执行走 `policy.evaluate()`。
禁止在工具内直接调用未经策略评估的命令。

### 三档分级

- `ALLOW`：只读白名单命令命中 → 直接执行
- `ASK`：有副作用、未知命令 → **放行执行**（由客户端 UI 弹窗让用户把关确认；服务端记录结构化审计日志）
- `DENY`：明确禁止（破坏系统等高危操作）→ 绝对阻断拒绝

### 关键约束

- 客户端（如 Kelivo）原生支持在客户端 UI 开启工具级执行前审批确认（Client-side confirmation），因此服务端不必也不能触发反向审批回调。
- 服务端以 `DENY` 为不可逾越的底线；`ASK` 档位放行执行并在后台记录审计日志。
- 命令执行禁止无约束注入拼接。
- 新增规则只改 `policy.py` 的正则列表，并在 `tests/test_policy.py` 补用例。

## 7. 任务执行机制

### 实时执行（短任务 <= 8 秒）
- 工具：`run_command(command, cwd=".", timeout=60.0)`
- 行为：同步等待进程结束或超时，直接返回 output、exit_code、duration。支持超长输出折叠。
- 绝不返回冗余 summary 字段，只返回纯数据字段。

### 异步长任务（耗时任务 > 8 秒）
- 编译、构建、安装依赖、长期运行服务或预计大于 8 秒的任务，走后台异步管理。
- `run_background_command(command, cwd)` → 立即返回 `task_id`，不阻塞主线程
- `get_task_status(task_id)` → 只读查询，返回 running/done/failed/denied 及输出
- `list_tasks()` → 只读列出任务
- `cancel_task(task_id)` → 终止任务，`terminate` → `wait(timeout)` → `kill` 三段式杀进程
- TTL 清理只针对 `done` / `failed` / `canceled` / `denied`，**running 任务绝不清**

## 8. 响应与日志规范（极致节省 Token）

所有工具返回保持纯净数据结构，禁止返回 summary 字符串：

```json
{
  "status": "success | error | timeout | denied",
  "output": "终端输出",
  "exit_code": 0,
  "duration": 0.023
}
```

- 统一走 logging.structured，禁止自行 print

## 9. 批量与并发

- 只读工具支持批量参数（list[str]），内部用 ThreadPoolExecutor 并发
- 优先批量并发处理，减少网络往返与上下文开销

## 10. 客户端适配（Kelivo）

- 审批是工具级手动开关，用户在 UI 上单独开启（由客户端把关 ASK 级风险）
- 支持 GET /mcp 建立 SSE 流式长连接 (200 OK + text/event-stream) 与心跳，允许客户端正常握手与断线重试
- 服务重启后自动接纳恢复客户端已有的 Mcp-Session-Id，避免 400 阻断
- POST /mcp 为主数据通道

## 11. 测试

新增或修改代码必须补测试，make check 必须通过。

- Makefile：`make check` 运行全量测试。
- 禁止提交未通过 make check 的代码。
