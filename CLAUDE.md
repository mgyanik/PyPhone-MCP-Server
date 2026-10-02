# 项目约定 — phone-mcp-server

本文件是 agent 修改本项目时必须遵守的规范。改代码前先读完。
与本文件冲突的“通用最佳实践”，一律以本文件为准。

## 1. 项目定位

MCP Server，向 LLM 客户端（当前主要客户端：Kelivo）暴露语义化工具，
用于读取文件、搜索、执行命令与异步长任务管理。

四个核心目标：
1. 工具语义清晰，LLM 能准确选择
2. 风险分级明确，服务端为唯一防线
3. 日志结构化，人类可读可审计
4. 操作可 diff、可回滚、可验证

## 2. 双栈现状

- Node 版：`server.js`，监听 3000 端口，历史遗留，计划退役
- Python 版：`src/server.py`，监听 3001 端口，当前主力
- 迁移完成后 Node 版本下线，只保留 Python 版
- 开发时只碰 Python 版，不要给 Node 版加新功能

## 3. 目录结构

```
src/
  server.py       # MCP Streamable HTTP 服务入口，监听 3001
  registry.py     # 工具注册表与 schema 生成
  policy.py       # 策略引擎（ALLOW / ASK / DENY）
  task_store.py   # 异步长任务存储与生命周期
  logging.py      # 结构化日志
  tools/          # 一文件一工具
    get_file.py
    list_dir.py
    search_text.py
    start_task.py
    get_task_status.py
    list_tasks.py
    cancel_task.py
tests/
  test_annotations.py
  test_policy.py
  test_tasks.py
  test_server.py
Makefile          # make check 一键回归
CLAUDE.md         # 本文件
```

新增工具只在 `src/tools/` 下新建文件，并在 `registry.load_tools()` 注册。

## 4. 工具命名

| 操作 | 前缀 | 示例 |
|---|---|---|
| 读取单个 | `get_` | `get_file` |
| 列出 | `list_` | `list_dir` |
| 搜索 | `search_` | `search_texts` |
| 执行命令 | `run_` | `run_safe_command` |
| 任务启动/查询/取消 | `start_` / `get_` / `cancel_` | `start_task` |

禁止：
- 泛化名：`read`、`write`、`process`、`do`、`handle`、`exec`
- 读写合并进同一工具
- 中性名掩盖副作用
- 同一功能同时注册单数版和复数版（只注册批量版，单数是内部函数）

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
禁止在工具内直接调用 `subprocess`、`os.system`、`shell=True`。

### 三档分级

- `ALLOW`：只读命令白名单命中 → 直接执行
- `ASK`：有副作用、未知命令 → **拒绝执行**，返回 `denied` 并提示用户手动运行
- `DENY`：明确禁止（`rm -rf /` 等）→ 直接拒绝

未知命令默认 `ASK`，禁止默认放行。

### 关键约束

- 由于 Kelivo 不支持服务端触发的审批回调，**ASK 语义是“拒绝执行”**，
  不是“等待用户确认后执行”。不要设计 confirm_command 闭环，
  Kelivo 客户端不会调用它。
- 命令执行用 `shell=False` + token 列表，禁止字符串拼接
- 新增规则只改 `policy.py` 的正则列表，并在 `tests/test_policy.py` 补用例

## 7. 异步长任务

编译、测试、构建、安装依赖等耗时任务，一律走 `task_store`。

### 接口

- `start_task(command, cwd)` → 立即返回 `task_id`，不阻塞
- `get_task_status(task_id)` → 只读查询，返回 running/done/failed/denied
- `list_tasks()` → 只读
- `cancel_task(task_id)` → 终止任务，三段式杀进程

### 约束

- `spawn()` 必须先调 `policy.evaluate()`：DENY 拒绝，ASK 拒绝，ALLOW 才启动
- 后台线程监控进程，禁止阻塞主线程
- TTL 清理只针对 `done` / `failed` / `canceled`，**running 任务绝不清**
- `cancel()` 必须 `terminate` → `wait(timeout)` → `kill` 三段式

## 8. 日志

所有工具返回必须结构化：

```json
{
  "status": "ok | denied | needs_confirmation | error",
  "summary": "一句人类可读的描述",
  "data": {},
  "duration_ms": 123
}
```

- summary 必填
- 写操作返回 diff
- 统一走 logging.structured，禁止自行 print

## 9. 批量与并发

- 只读工具支持批量参数（list[str]），内部用 ThreadPoolExecutor 并发
- 只注册批量版（复数名），单数版作为内部函数
- 工具描述里明确“可一次传入多个目标，比逐个调用更快”
- 写工具处理同一资源并发写（加锁或返回冲突）

## 10. 客户端适配

### Kelivo（当前主客户端）

- 不消费 annotations（readOnlyHint / destructiveHint 无效）
- 审批是工具级手动开关，用户在 UI 上单独开启
- 不支持服务端触发的确认回调
- initialized 后会尝试 GET /mcp 建立 SSE 长连接
  - server 返回 405 使其立即退出（不要返回 5xx，会死循环重试）
- POST /mcp 是唯一实际数据通道

不要为了兼容某个客户端而破坏 MCP 规范。

## 11. 测试

新增或修改代码必须补测试，make check 必须通过。

必须存在：
- test_annotations.py：遍历所有工具断言 annotations 齐全
- test_policy.py：三档分级正反用例
- test_tasks.py：任务生命周期
- test_server.py：GET 405 / POST 200

禁止提交未通过 make check 的代码。

## 12. Agent 修改流程

1. 读本文件 + 相关模块
2. 明确改哪个文件、属于哪一层
3. 按规范实现
4. 补测试
5. 运行 make check
6. 失败自行修复后重跑，直到通过
7. 汇报：文件列表 + diff 摘要 + make check 原始输出

禁止：
- 不读本文件直接改
- 新增工具却不注册、不补测试
- 绕过 policy 直接执行命令
- 提交未通过 make check 的代码

## 13. 冲突处理

本文件与“通用最佳实践”冲突时，以本文件为准。
认为某条不合理，先提出，不要擅自绕过。
