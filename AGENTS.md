# AGENTS.md — error-backends（错误后端）项目知识库

给 AI 代理与本仓库维护者的项目说明。改代码前先读这份文件。

## 项目是什么

海豹插件配套的后端管理框架，采用**独立分发**模式：

- 仓库维护注册表索引 `backends.json` 与程序商店 `backends/<name>/`（git 保留，永不删除）
- 后端程序按需从商店复制到运行目录 `installed/<name>/`（gitignore）；商店缺文件时从远端拉取
- 依赖随安装/卸载/更新生命周期自动管理，不提供手动装/卸依赖的入口
- WebUI 管理界面（`webui.py`，纯标准库）+ 命令行工具（`errorbackend`）+ 进程守护 + 版本更新检查

当前已收录后端：`ocr` / `redbag` / `run_shell` / `chart`（见 `backends.json` 索引）。

## 组件与文件

| 文件 | 职责 |
| --- | --- |
| `launcher.py` | 核心入口：后端发现（`backends/`）、安装/卸载、依赖、启停、更新、WebUI、打包、systemd |
| `webui.py` | Web 管理界面：内嵌 HTML/CSS/JS（`PAGE`）+ 标准库 HTTP 服务 |
| `errorbackend.py` | 命令行工具（复用 launcher 逻辑） |
| `install_cli.py` | 安装 `errorbackend` 到 PATH（launcher 每次启动自动调用，幂等） |
| `backends.json` | 注册表索引：`name/description/type/entry/deps/port/version/source/files` |
| `backends/<name>/` | 后端程序包目录（安装时按需下载；含 `backend.json` 清单） |
| `CHANGELOG.md` / `VERSION` | 更新日志 / 版本号（release 由 tag 写入） |
| `launcher.json` | 全局配置：`auto_restart`、`restart_backoff_seconds`、`log_dir` |

## 数据与状态（均 gitignore）

- `.runtime.json`：后端运行时配置 `config/<name> = {port, token, host}` + `webui = {port, host, token}`；读写统一走 `launcher.backend_config()` / `save_backend_config()` / `configure_webui_*()`
- `logs/state.json`：Supervisor 进程状态；`logs/webui.pid`：后台 WebUI 进程号（格式 `pid host port`）；`logs/<name>.log`：后端日志
- `backends/<name>/.venv` / `node_modules` / `lang-data` / `cache` / `temp_images`：运行时产物，不入库、不进发布包

## 关键流程

### 后端发现
`launcher.discover_backends()` 只扫描 `backends/*/backend.json`（`PACKAGES_DIR`）。WebUI 的 `/api/backends` 会把注册表（`load_registry()`）里**未安装**的后端也并进来（`installed: false`），卡片显示「安装」。

### 安装（`install_backend` / WebUI「安装」/ `install-backend` 命令）
注册表条目 → 从商店 `backends/<name>` 按 `files` 清单复制到 `installed/<name>/`（商店缺文件时从 `source` 远端下载）→ 写 `backend.json`（缺省时）→ `setup_backend()` 装依赖（失败自动清理半成品，回到未安装）。WebUI 侧走 `start_install()`（后台 `launcher.py install-backend <name>`，日志轮询 `/api/setup-log/<name>`，安装中卡片转圈 + 日志）。

### 卸载（`remove_backend_dir` / WebUI「卸载」/ `uninstall-backend` 命令）
停止后端 → 删除 `installed/<name>`（程序 + 依赖）。**git 商店 `backends/<name>` 永远不删**。WebUI 卸载为异步（卸载中转圈 + 日志），完成后卡片回到「安装」。

### 更新
- 整体：「⬆ 更新」→ `update_project()`（git pull）→ 先停全部 → 逐后端 `setup_backend()` 同步依赖 → 再启动依赖就绪的后端 → WebUI 2 秒后自动重启
- 单个：卡片「⬆ 更新」→ `POST /api/update-backend/<name>` → git pull → 停止 → `setup_backend()` 同步依赖 → 重启该后端
- 依赖精确同步：Python 依赖清单（`requirements.txt`）变化时删除并重建 venv；Node 有 `package-lock.json` 时用 `npm ci`（无则 `npm install`），保证依赖不多不少
- 版本检查：`launcher.update_check()`（60 秒缓存）`git fetch` 后对比本地/远端 `backend.json` 的 `version`，返回 `{repo_update, backends:{name:{local,remote,available}}}`；失败返回空（前端静默）

### WebUI 启动 / CLI 自动安装
`main()` 最先 `ensure_cli_installed()`（写 shim + PATH，幂等）→ `cleanup_legacy_backend_dirs()`（升级清理：git 已不跟踪的旧版顶层后端目录整目录删除，防残留）→ plain run 自动生成 WebUI 端口/token 并后台启动后退出。自动开浏览器仅限 Windows 或显式设置 `$BROWSER` 的 Linux/macOS。

## WebUI API

除 `/`（登录页）与 `/icon*.png` 外，请求需带 `Authorization: Bearer <token>` 或 `X-Token: <token>`。

- `GET /api/backends`：已安装（`installed/` 中程序 + 依赖就绪）+ 注册表未安装卡片数据，含 `updates` 版本检查结果
- `GET|POST /api/config/<name>`、`POST /api/port/<name>[/reset]`：后端端口/token/host 配置
- `GET /api/config/<name>` 额外返回 `options`（自定义配置值与默认值合并）与 `config_schema`（来自 `backend.json` 的 `config` 字段）；`POST` 接受 `options`，按 schema 校验并保存到 `.runtime.json` 的 `config/<name>.options`
- `POST /api/install/<name>`：后台安装（轮询 `/api/setup-log/<name>`）
- `POST /api/uninstall/<name>`：停止 + 删除程序与依赖
- `POST /api/start-all|stop-all|restart-all|start/<name>|stop/<name>|restart/<name>`
- `POST /api/update-backend/<name>`：单独更新后端（拉代码 + 检查依赖 + 重启）
- `POST /api/update`：整体更新（成功后重启全部后端）
- `GET /api/webui-token` / `POST /api/webui-token`（`{token}` 或 `{reset:true}`）、`POST /api/webui-restart`
- `GET /api/logs/<name>`、`GET /api/setup-log/<name>`（安装/卸载日志轮询）

## 开发约定

- WebUI 保持纯标准库；后端依赖只在各自 venv/node_modules，不要手动装
- 改 `webui.py` 的 `PAGE`（内嵌 HTML/JS）后，必须用 `python -c "import webui; ..."` 取出 PAGE 并 `node --check` 验证 JS；PAGE 是 Python 字符串，JS 里要输出的 `\n` 必须写成 `\\n`（单反斜杠会被 Python 转成真实换行、直接弄坏页面脚本）
- 新增后端 = `backends/<name>/`（含 `backend.json`，必须有 `version`）+ `backends.json` 注册表条目（`files` 清单要与包目录同步）
- 自定义配置：`backend.json` 的 `config` 声明 `{key: {label, type, default, env}}`，`launcher.Supervisor.spawn` 会把保存值（或默认值）以 `env` 注入；改配置后需重启后端生效
- UI 不提供手动「安装依赖 / 删除依赖」入口，依赖只随安装/卸载/更新
- 后台子进程 Windows 下必须带 `CREATE_NO_WINDOW`：统一用 `launcher._no_window_kwargs()`；新增 subprocess 调用后 `rg -n "subprocess"` 排查
- 日志统一 UTF-8：子进程环境加 `PYTHONIOENCODING=utf-8`、`PYTHONUTF8=1`
- 运行时配置读写只通过 `launcher.backend_config()` / `save_backend_config()` / `configure_webui_*()`
- 命令行与 WebUI 共用同一套进程与状态（`logs/state.json`）；新增子命令要同步 `launcher.py` + `errorbackend.py` + README/AGENTS
- 端口约定：WebUI 随机五位数；新增后端默认端口避开本机已有服务端口与已收录后端端口（当前 ocr 18699 / redbag 3000 / run_shell 3011 / chart 3003）
- 更新日志写入 CHANGELOG.md（日常在 `Unreleased`）

## 常用排查

- 后端起不来：`logs/<name>.log`；安装日志看 `/api/setup-log/<name>`
- 安装失败：检查注册表 `source`/`files` 与远端是否一致；远端不可用时需本地有同路径副本
- 端口/配置不生效：`.runtime.json` 覆盖默认值，改完重启后端
- WebUI 黑框：后台子进程缺 `CREATE_NO_WINDOW`
- `errorbackend` 失效：重跑 `python install_cli.py`
