# AGENTS.md — error-backends（错误后端）项目知识库

给 AI 代理与本仓库维护者的项目说明。改代码前先读这份文件，能省掉大量上下文。

## 项目是什么

错误后端的配套后端管理仓库：一个 launcher 管理若干 HTTP/MCP 后端服务（当前已收录 `ocr` / `redbag` / `run_shell` / `chart`），提供：

- WebUI 管理界面（`webui.py`，纯 Python 标准库，无第三方依赖）
- 命令行管理工具（`errorbackend`，类似 pm2）
- 按需安装依赖（Python 后端独立 venv / Node 后端 `node_modules`，不预装全部）
- 进程守护：异常退出自动拉起，卡片展示运行时长/内存/自动拉起次数
- 发布：Git tag 触发 GitHub Actions 自动打包 zip + tar.gz 并发布（含更新日志）

## 快速启动

```bash
python launcher.py                     # 首次自动装依赖并后台启动 WebUI（端口/token 随机生成，以启动输出为准）
python launcher.py webui-stop          # 停止后台 WebUI
python install_cli.py                  # 安装 errorbackend 命令（Windows 生成 .cmd，Linux 写入 shell 配置）
errorbackend help                      # 查看所有命令
```

## 组件与文件

| 文件 | 职责 |
| --- | --- |
| `launcher.py` | 核心入口：后端发现/启停/依赖安装/运行时配置/WebUI 启停/更新/打包/systemd 服务 |
| `webui.py` | Web 管理界面：内嵌 HTML/CSS/JS（`PAGE` 常量）+ 标准库 HTTP 服务 |
| `errorbackend.py` | 命令行工具（复用 launcher 逻辑），彩色 help |
| `install_cli.py` | 安装 `errorbackend` 到 PATH（Windows `~/.errorbackend/bin/errorbackend.cmd` / Linux shell 脚本）；launcher 每次启动自动调用 `install()`（幂等，不重复写 PATH） |
| `backends/*/backend.json` | 后端清单：`name` / `type`(python\|node) / `entry` / `deps` / `port` / `description`（目录在仓库根目录，当前收录 `ocr` / `redbag` / `run_shell` / `chart`） |
| `CHANGELOG.md` | 更新日志：`## <版本号>` 段落，release 与更新弹窗都从这里取 |
| `VERSION` | 当前版本号（release 时由 tag 写入） |
| `launcher.json` | 全局配置：`auto_restart`、`restart_backoff_seconds`、`log_dir` |

## 数据与状态文件（logs/ 与根目录，均 gitignore）

- `.runtime.json`：每后端运行时配置 `config/<name> = {port, token, host}`；`ports` 为旧版字段（读兼容、写同步）；`webui` 为 WebUI 管理界面配置：`port`（首次运行随机生成五位数，避开已收录后端端口）、`host`（默认 0.0.0.0）、`token`（首次运行自动生成），命令行 `webui-port` / `webui-host` / `webui-token` 读写，修改后自动重启 WebUI。读写统一走 `launcher.backend_config()` / `save_backend_config()` / `configure_webui_port()` / `configure_webui_host()` / `configure_webui_token()`。
- `logs/state.json`：Supervisor 进程状态（`pid`、`started_at`、`restarts`、`stopped` 标记）。
- `logs/webui.pid`：后台 WebUI 进程号（格式：`pid host port`，兼容旧版纯 pid；`stop_webui` 只取第一段）。
- `logs/<backend>.log`：各后端日志；`logs/webui.log`：WebUI 日志。

## 关键流程

### 一键启动（`python launcher.py`）
`ensure_webui_deps()`（无 webui-requirements.txt 时为空操作）→ `start_webui_background()`：检测 pid 文件避免重复启动；首次运行自动生成访问 token（`effective_webui_token()`，secret 保存于 `.runtime.json` 的 `webui.token`）；detach 子进程（Windows `DETACHED_PROCESS | CREATE_NO_WINDOW`，Linux `start_new_session`）；打印访问地址与 token；自动开浏览器仅限 Windows，Linux/macOS 必须显式设置 `$BROWSER` 且存在 DISPLAY/WAYLAND_DISPLAY 才尝试（SSH -X 不会误触发，避免 xdg-open 报错）；命令执行完即退出，WebUI 留在后台。

### CLI 自动安装（每次启动 launcher 都会执行）
`main()` 最先调用 `ensure_cli_installed()` → `install_cli.install()`：写 shim（Windows `.cmd` / Linux shell 脚本）→ 加入 PATH（Windows 注册表 + `WM_SETTINGCHANGE` 广播刷新；Linux 写入 `.bashrc`/`.zshrc`/`.profile`，已包含则跳过，避免重复追加）。改 install_cli 逻辑后，`launcher.py` 与 `errorbackend.py` 两侧入口都要保持一致。

### 后端启动（`Supervisor.spawn`）
按需安装依赖（首次）→ Linux 下 node 后端自动检测/补齐 Puppeteer Chromium 系统库（`ldd` 找 missing，Debian/Ubuntu 用 `apt-get` 自动装，映射见 `_PUPPETEER_LIB_PACKAGES`）→ 注入环境变量 `ERROR_BACKEND_PORT / _HOST / _TOKEN`（值来自 `.runtime.json`）→ 子进程日志重定向到 `logs/<name>.log`，`CREATE_NO_WINDOW`。`_monitor` 线程负责异常退出后按退避时间自动拉起；手动停止写入 `stopped` 标记则不再拉起。

### 后端 token/监听 IP
后端读取 `ERROR_BACKEND_HOST`（默认 `0.0.0.0`）与 `ERROR_BACKEND_TOKEN`（默认空）。token 非空时校验请求头 `Authorization: Bearer <token>` 或 `X-Token: <token>`，否则 401。已收录后端都要按此接入（Flask/FastAPI 中间件、express 中间件、MCP 的 ASGI 包装，参考已收录后端或常见框架模式）。

### 更新（`errorbackend update` / WebUI「⬆ 更新」）
`launcher.update_project()`：记录旧 HEAD → `git pull --ff-only` → HEAD 未变则 `updated=False`（前端弹「没有可以更新的」）；有更新则用 `_update_changelog()` 收集 CHANGELOG.md 里「旧 HEAD 没有且高于当前 VERSION」的版本段落，取不到则退回 `git log`。

### Linux systemd 服务
`python launcher.py service-install`（或 `errorbackend service-install`）：停止旧后台 WebUI → 生成 unit（前台跑 `launcher.py webui --no-browser`，`Restart=always`，服务名 `error-backends-webui`）→ `systemctl enable --now`。非 root 自动加 sudo；无 systemctl（SysV/Upstart/OpenRC）时明确报错退出。

### 发布
Git tag `v*` 触发 `.github/workflows/release.yml`：tag 去掉 `v` 写进 VERSION → `launcher.py package` 生成 `dist/error-backends-<version>.zip/.tar.gz` → 从 CHANGELOG.md 按版本号提取段落作为 release 描述。发版前记得把 CHANGELOG 的 `Unreleased` 改成版本号并补日期。

## WebUI API

除 `/`（页面）与 `/icon.png` / `/icon-256.png`（图标）外，所有请求需带 `Authorization: Bearer <token>` 或 `X-Token: <token>`（token 为空时不校验）。

- `GET /api/backends`：卡片数据（含 `port`/`host`/`token`/`running`/`uptime_secs`/`restarts`/`mem_*`/`deps_ready`）
- `POST /api/update-backend/<name>`：拉取代码（git pull）→ 检查/安装依赖 → 重启该后端
- `POST /api/delete-backend/<name>`：停止后端 → 删除依赖 → `git rm` 并删除整个后端目录
- `GET /api/webui-token`：查看当前 WebUI token；`POST /api/webui-token`：body `{token}` 修改或 `{reset:true}` 重新随机生成（改完立即生效，无需重启）
- `POST /api/webui-restart`：重启 WebUI（响应先返回，随后由独立进程执行 `launcher.py webui-restart`，用于重新加载后端清单）
- `GET|POST /api/config/<name>`：查询/保存 {port, token, host}
- `POST /api/port/<name>`、`/api/port/<name>/reset`：旧版端口接口（写同一份配置，保留兼容）
- `POST /api/setup/<name>`、`/api/deps-delete/<name>`、`GET /api/setup-log/<name>`：依赖安装/删除/日志轮询
- `POST /api/start-all` / `stop-all` / `restart-all` / `start/<name>` / `stop/<name>`
- `POST /api/update`：更新，返回 `{ok, updated, changelog, output}`
- `GET /api/logs/<name>`：后端日志（末 300 行）

## 开发约定

- WebUI 必须保持纯标准库（不引入 webui-requirements.txt）；后端依赖只在各自 venv/node_modules 按需安装，不要手动装。
- 新增后端 = 新建目录 + `backend.json`（含默认端口）+ 入口脚本读取 `ERROR_BACKEND_PORT`；如需 token/监听 IP 支持，按上面「后端 token/监听 IP」的模式接入 `ERROR_BACKEND_TOKEN/_HOST`。
- 确保不弹黑框：任何在 WebUI/后台（无控制台）进程里执行的子进程调用，Windows 下必须带 `CREATE_NO_WINDOW`——统一用 `launcher._no_window_kwargs()` 注入，新增 git 命令一律走该辅助函数；改完用 `rg -n "subprocess"` 排查所有调用点，逐处确认。
- 日志统一 UTF-8：子进程环境加 `PYTHONIOENCODING=utf-8`、`PYTHONUTF8=1`（同 `Supervisor.spawn` 的写法）。
- 运行时配置读写只通过 `launcher.backend_config()` / `save_backend_config()`，不要直接改 `.runtime.json` 结构。
- WebUI 的端口/监听地址/访问 token 配置统一走 `launcher.configure_webui_*()`，`launcher.py` 与 `errorbackend.py` 都要有对应子命令（`webui-port` / `webui-host` / `webui-token`），改后自动重启 WebUI。
- 新增「重启 WebUI」入口时三处同步：WebUI 页面按钮（`POST /api/webui-restart`）+ `launcher.py webui-restart` + `errorbackend.py webui-restart`。
- 后端版本号：`backend.json` 必须带 `version` 字段；更新检查走 `launcher.update_check()`（git fetch 对比，60 秒缓存，失败返回空）。
- 端口约定：WebUI 端口首次运行随机生成（10000-65535，避开已收录后端端口）；新增后端默认端口避开本机已有服务端口，也不与本项目已有后端重复（当前 `ocr` 18699 / `redbag` 3000 / `run_shell` 3011 / `chart` 3003）。
- 命令行与 WebUI 共用同一套后端进程与状态（`logs/state.json`），改动两处入口都要同步（如新增子命令：`launcher.py` + `errorbackend.py` + README）。
- 平台差异：Windows 与 Linux 行为保持一致；系统服务类命令在非 Linux 平台提示「仅支持 Linux」并不展示在 help（`errorbackend` 的 cmd_help 按 `os.name` 过滤）。
- 更新日志：改动记录进 CHANGELOG.md（日常写在 `Unreleased`）。

## 常用排查

- 后端起不来：看 `logs/<name>.log`；依赖没装完看 WebUI 安装日志（`/api/setup-log/<name>`）。
- 端口被占/生效的是旧值：`.runtime.json` 里 `config/<name>.port` 覆盖默认端口，改完需重启后端。
- WebUI 黑框：后台场景子进程缺 `CREATE_NO_WINDOW`；点击更新弹黑框是 `update_project()` 的 `git pull` 缺该标志。
- errorbackend 命令失效：重新跑 `python install_cli.py`（改 shim 生成逻辑后必须重装）。
