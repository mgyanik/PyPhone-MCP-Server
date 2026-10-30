# 项目约定 — PyPhone-MCP-Server

本文件是 Agent 维护本项目时必须遵守的规范。改动代码必须回读验证，并运行 `make check`（需先安装 pytest，安装后以此为唯一通过判据）。

## 1. 项目定位与核心指标

专为 Android / Termux 环境打造的轻量、高性能 MCP (Model Context Protocol) Streamable HTTP 服务端。

- 零外部运行时依赖：生产环境严格基于 Python 3.10+ 标准库。
- 单端口架构：MCP 协议服务默认监听 3000 端口；不提供 WebUI 审批台与通用命令执行工具。
- 紧凑输出：纯净结构化数据返回，保护上下文 Token。

## 2. 目录架构

```
src/
  __init__.py               # 包标记，缺失会导致 python3 -m src.server 报 No module named src.server
  config.py                 # 全局运行配置、环境变量与沙箱根路径
  server.py                 # MCP HTTP/SSE 协议传输层入口 (端口 3000)
  registry.py               # MCP 工具注册中心与兼容别名映射
  core/
    protocol.py             # JSON-RPC 2.0 与 MCP 协议消息定义
    session.py              # 客户端会话管理
    security.py             # 路径沙箱解析与安全校验 (resolve_safe_path)
    logging.py              # 结构化日志
  tools/
    edit_file.py            # patch_file (结构化局部补丁与范围覆写)
    find_process.py         # find_process (免 root 排查进程与网络监听端口)
    get_file_info.py        # inspect_file_meta (文件元数据与 SHA-256 校验)
    list_dir.py             # list_directory (并发目录枚举)
    manage_file.py          # move_or_delete_file (安全移动/复制/删除文件与目录)
    read_file.py            # read_file_or_outline (智能文件读取与大纲解析)
    search_text.py          # search_codebase (代码库并发关键词检索)
    take_github.py          # take_github (统一 Git 与 GitHub CLI 操作网关)
tests/                      # 自动化测试用例集
Makefile                    # make check 一键回归验证
pyproject.toml              # 项目元数据与打包配置
py-mcp.sh                   # 守护进程管理脚本 (start/stop/restart/status/logs)
```

## 3. 工具矩阵

| 工具名 (主名) | 兼容别名 | 关键指引与约束 |
|---|---|---|
| `patch_file` | `edit__file` | 结构化文件编辑。支持搜索替换、行号范围精准替换、全量覆写或缺失新建；禁止无故全量重写大文件 |
| `read_file_or_outline` | `read_file`, `read_file_lines` | 智能文件读取。大文件优先返回结构大纲，支持按行范围切片读取，节省 Token |
| `search_codebase` | `search_text` | 关键词并发全文检索。自动剪枝 `.git` 与依赖目录，支持单词或列表检索 |
| `list_directory` | `list_dir`, `MCP__list_dir` | 并发目录枚举。结果上限 1000 项以保护上下文；海量文件场景优先使用 search_codebase |
| `inspect_file_meta` | `get_file_info` | 查询文件大小、权限模式、最后修改时间及按需计算 SHA-256 哈希 |
| `move_or_delete_file` | `manage_file` | 安全移动、复制、删除文件与目录，内置系统根目录防误删与沙箱检查 |
| `find_process` | - | 免 root 解析 `/proc` 排查活跃进程与网络端口，替代 lsof/netstat |
| `take_github` | - | 统一 Git 与 GitHub CLI (gh) 操作网关。完全开放 git 与 gh 母命令与全部子命令权限，支持传入 command 完整命令行或结构化参数 |

## 4. 核心安全机制

- 路径沙箱：所有文件读写必须通过 `resolve_safe_path` 严格约束在 `TERMUX_HOME`（`/data/data/com.termux/files/home`）内，采用 `realpath` + `commonpath` 判定，阻断 `..` 相对越界、软链接逃逸与同前缀路径（如 `home_evil`）绕过。`move_or_delete_file` 额外拒绝删除或移动沙箱根自身。
- Git/GitHub 执行控制：完全开放 git 与 gh 工具权限，git 与 gh 采用参数列表直接执行，杜绝 shell 逃逸注入；破坏性操作与远程写操作由模型在会话中直接向用户提出并获得明确确认后执行。
- 命令执行面：项目不提供通用 Shell 命令工具（`request_tool` 已移除），MCP 端仅能执行 git 与 gh。`make check`、`pkg`、`pip` 等命令须由用户在终端手动执行。
- 传输层防护：单连接静默等待上限 75s（`MCPRequestHandler.timeout`）；监听 backlog 128（`MCPHTTPServer.request_queue_size`）；并发 SSE 连接上限 16，超限返回 503；单次 POST 请求体上限 4MB，超限返回 413；显式拒绝 `Transfer-Encoding: chunked` 与非对象 JSON 载荷；SSE 保活循环改用 `select` 探测断连并设 600s 最长存活，连接名额在 `finish()` 中保证释放。
- 端口探测降级：`find_process` 在 `/proc/net/tcp` 或 `/proc/<pid>/fd` 不可读时返回 `status: degraded` 并附 `warnings`，不再静默返回空结果。
- 访问控制：MCP 端点默认监听 `0.0.0.0`，设置 `MCP_AUTH_TOKEN` 后要求 `Authorization: Bearer <token>`，缺失或错误返回 401；未设置令牌时仅接受回环地址。项目已无 WebUI 审批台。
- 注册表契约：工具重名注册直接抛错；调用时传入未知参数抛错（`_` 例外，兼容部分平台注入的占位键）；`annotations`（如 `readOnlyHint`）随 `tools/list` 下发。

## 5. 开发者与 Agent 工作规范

维护或开发本项目时，必须严格执行以下流程：
1. 分析相关代码，说明现状与问题；
2. 给出具体修改方案及影响范围；
3. 等待用户确认；
4. 确认后再执行修改；
5. 修改完成后必须回读验证，并运行针对性测试：
```bash
make check   # 唯一通过判据
```
   测试基线现状：已重建为 `tests/test_tools.py`（9 工具契约）、`tests/test_registry.py`（注册表契约）、`tests/test_server.py`（传输层）、`tests/conftest.py`（sys.path 注入），当前 22 项全部通过。pytest 安装在 `python3.14` 解释器下，`Makefile` 已固定 `PYTHON ?= python3.14`；若切换解释器用 `make PYTHON=python3`。`make check` 是唯一通过判据，不得凭空声称已通过。
未经用户明确确认，不得直接改动代码或执行提交/推送。
