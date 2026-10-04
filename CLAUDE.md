# 项目约定 — PyPhone-MCP-Server

本文件是 Agent 维护本项目时必须遵守的规范。改动代码必须保证 `make check` 全量通过。

## 1. 项目定位与核心指标

专为 Android / Termux 环境打造的轻量、高性能 MCP (Model Context Protocol) Streamable HTTP 服务端。

- 零外部运行时依赖：生产环境严格基于 Python 3.10+ 标准库。
- 双端口架构：MCP 协议服务默认监听 3000 端口，WebUI 命令审批控制台监听 8080 端口。
- 紧凑输出：纯净结构化数据返回，保护上下文 Token。

## 2. 目录架构

```
src/
  config.py                 # 全局运行配置、环境变量与沙箱根路径
  server.py                 # MCP HTTP/SSE 协议传输层入口 (端口 3000)
  webui.py                  # 独立 WebUI 审批控制台 (端口 8080，含规则管理与执行日志)
  registry.py               # MCP 工具注册中心与兼容别名映射
  core/
    protocol.py             # JSON-RPC 2.0 与 MCP 协议消息定义
    session.py              # 客户端会话管理
    pool.py                 # 全局常驻高并发工作线程池
    security.py             # 路径沙箱解析与安全校验 (resolve_safe_path)
    auth_store.py           # WebUI 审批持久化存储 (pending/whitelist/blacklist/exec_log)
    task_store.py           # 异步任务持久化与生命周期管理
    logging.py              # 结构化日志
  tools/
    edit_file.py            # patch_file (结构化局部补丁与范围覆写)
    find_process.py         # find_process (免 root 排查进程与网络监听端口)
    get_file_info.py        # inspect_file_meta (文件元数据与 SHA-256 校验)
    list_dir.py             # list_directory (并发目录枚举)
    manage_file.py          # move_or_delete_file (安全移动/复制/删除文件与目录)
    read_file.py            # read_file_or_outline (智能文件读取与大纲解析)
    request_tool.py         # request_tool (统一系统命令执行网关，受 WebUI 审批控制)
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
| `request_tool` | - | 统一系统命令执行网关。未知命令须经 WebUI 审批，支持 shell=True 管道受控执行，自动记录执行审计日志 |
| `find_process` | - | 免 root 解析 `/proc` 排查活跃进程与网络端口，替代 lsof/netstat |
| `take_github` | - | 统一 Git 与 GitHub CLI (gh) 操作网关。完全开放 git 与 gh 母命令与全部子命令权限，支持传入 command 完整命令行或结构化参数 |

## 4. 核心安全机制

- 路径沙箱：所有文件读写必须通过 `resolve_safe_path` 严格约束在 `TERMUX_HOME`（`/data/data/com.termux/files/home`）内，阻断 `..` 相对越界与非法绝对路径访问。
- 命令审批：系统命令统一收敛至 `request_tool`。未知命令先提交待审批，由管理员在 WebUI（端口 8080）显式批准后方可执行；规则支持原子持久化与自动去重；执行后自动追加执行审计日志。
- Git/GitHub 执行控制：完全开放 git 与 gh 工具权限，彻底免除日常开发在 WebUI 堆积命令审批的负担。母命令严格限定为 git 与 gh 并采用参数列表直接执行，杜绝 shell 逃逸注入；远程写操作由模型在会话中直接向用户提出并获得明确确认后执行。

## 5. 开发者与 Agent 工作规范

维护或开发本项目时，必须严格执行以下流程：
1. 分析相关代码，说明现状与问题；
2. 给出具体修改方案及影响范围；
3. 等待用户确认；
4. 确认后再执行修改；
5. 修改完成后必须回读验证，并运行回归测试：
```bash
make check
```
未经用户明确确认，不得直接改动代码或执行提交/推送。
