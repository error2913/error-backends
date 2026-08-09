# error-backends（错误后端）

错误后端的配套后端管理框架：一个 launcher 统一管理若干 HTTP / MCP 后端服务，提供 WebUI 管理界面、命令行工具（`errorbackend`）、按需安装依赖与进程守护。

当前已收录后端：`ocr` / `redbag` / `run_shell` / `chart`。每收录一个后端，在仓库根目录新建一个目录并放入 `backend.json` 即可被自动发现，无需改 launcher 代码。

## 目录

- [快速开始](#快速开始)
- [跨平台](#跨平台)
- [Linux 系统服务](#linux-系统服务)
- [后端收录](#后端收录)
- [后端介绍](#后端介绍)
- [新增后端约定](#新增后端约定)
- [端口约定](#端口约定)
- [目录结构](#目录结构)
- [管理方式](#管理方式)
- [命令行（errorbackend）](#命令行errorbackend)
- [来源与许可](#来源与许可)

## 快速开始

环境要求：Python 3.9+；Node.js 20+（当前 `ocr` 后端要求）。

```bash
git clone https://github.com/error2913/error-backends.git && cd error-backends && python launcher.py
```

一条命令搞定全部：首次运行自动安装所需依赖、随机生成 WebUI 访问端口与 token，并在**后台启动**管理界面（不占用终端、无控制台窗口），命令执行完即退出。WebUI 默认监听 `0.0.0.0`，端口为首次运行随机生成的一个五位数（10000-65535），启动输出里会打印访问地址与 token。自动开浏览器仅限 Windows；Linux/macOS 必须显式设置 `BROWSER` 环境变量才会尝试（SSH -X 带过来的 DISPLAY 不会误触发）。launcher 每次启动还会**自动安装/刷新 `errorbackend` 命令行**（幂等，Windows / Linux 均适配），新打开的终端即可使用。停止后台 WebUI：`python launcher.py webui-stop` 或 `errorbackend webui-stop`。所有管理都在页面里完成：

- 首次启动某后端时，按钮显示「安装依赖」：点击后创建独立 venv / 执行 `npm install`，弹窗实时显示日志、按钮转圈，装完恢复为「启动」；之后再次启动不再安装，秒开
- 有后端依赖未安装时，右上角出现「安装全部依赖」，可一键补齐
- 「启动全部」只启动依赖已就绪的后端；若全部依赖未安装会弹出提示
- 「重启全部」先停止全部，再启动依赖已就绪的后端
- 右上角「⬆ 更新」从 Git 拉取项目更新（手动，非自动）
- 卡片显示运行时长、自动拉起次数与内存占用；「日志」旁可点「删除依赖」恢复未安装状态
- 卡片「⚙ 配置」弹窗可修改端口、访问 token 与监听 IP（默认 `0.0.0.0`），支持一键随机生成 token；token 默认留空 = 不鉴权
- 后端进程异常退出会自动拉起

> 按需安装：每个后端只安装自己缺失的依赖，不会预装全部；依赖清单（`requirements.txt` / `package.json`）变化后会自动重新安装。Python 后端使用独立 venv，Node 后端使用各自的 `node_modules`。

> WebUI 访问 token 首次运行自动生成；打开页面先出现 token 登录页，登录后浏览器记住一年；右上角「🔑 Token」可直接查看/修改/随机生成，`errorbackend webui-token` 命令行同样可改；接口请求可带 `Authorization: Bearer <token>` 或 `X-Token: <token>`。

## 跨平台

Windows 与 Linux 均支持，同一套代码无需改动：

- 依赖按平台处理：Python 后端用独立 venv（Windows 取 `.venv\Scripts\python.exe`，Linux 取 `.venv/bin/python`），Node 后端 Windows 下自动走 `npm.cmd`
- 后台守护：Windows 用 `DETACHED_PROCESS`（不弹控制台黑框），Linux 用 `start_new_session`
- 内存读取：Windows 走系统 API，Linux 读 `/proc`；运行时长/自动拉起次数两平台一致
- 安装 `errorbackend` 命令：Windows 生成 `errorbackend.cmd`，Linux 生成 shell 脚本并写入 shell 配置（`.bashrc` / `.zshrc` / `.profile`）；launcher 每次启动自动安装/刷新，无需手动执行，手动安装仍可用 `python install_cli.py`

## Linux 系统服务

注册 systemd 服务后，WebUI 开机自启、异常退出自动拉起（`Restart=always`）：

```bash
python launcher.py service-install      # 注册并立即启动（需 root/sudo）
python launcher.py service-uninstall    # 停止并移除服务
```

服务前台运行，日志通过 `journalctl -u error-backends-webui -f` 查看；安装服务前会自动停掉已有后台 WebUI 以释放端口。

## 后端收录

当前收录的后端：

| 目录 | 服务 | 默认端口 | 类型 |
| --- | --- | --- | --- |
| `ocr` | OCR 图片文字识别（tesseract.js） | 18699 | Node |
| `redbag` | 红包图片生成（FastAPI） | 3000 | Python |
| `run_shell` | Shell 命令执行并渲染输出为图片（仅 Linux） | 3011 | Python |
| `chart` | 排行榜图表图片生成（FastAPI） | 3003 | Python |

每收录一个后端，在仓库根目录新建一个目录并放入 `backend.json` 即可被自动发现（无需改 launcher 代码）；未收录任何后端时 WebUI 显示空态提示。

## 后端介绍

### ocr — OCR 图片文字识别

Node + tesseract.js 的本地 OCR 服务，接收图片 URL、base64 或本地路径，返回识别文字与置信度；任务串行执行（单 worker），并发请求自动排队。

- 默认端口 18699（Node / Express；与海豹插件默认「OCR 后端地址」一致，无需改插件配置）
- 接口：
  - `GET /health`：健康检查（含队列长度与默认语言）
  - `POST /api/ocr`：通用入口，body `{url | base64, mime?, lang?, psm?, whitelist?}`
  - `POST /api/ocr/url`：body `{url, lang?, psm?, whitelist?}`（支持 http(s)/file:///本机路径）
  - `POST /api/ocr/base64`：body `{base64, mime?, lang?, psm?, whitelist?}`
- 依赖：`express`、`tesseract.js`（Node >= 20）
- 语言包：首次识别按需下载到 `lang-data/`，也可先 `npm run setup-langs` 预下载（`eng,chi_sim`）；`lang-data/`、`cache/` 为运行时数据，不入库
- 环境变量：`ERROR_BACKEND_PORT` / `ERROR_BACKEND_HOST` / `ERROR_BACKEND_TOKEN`（launcher 注入），`OCR_DEFAULT_LANG`、`OCR_LANG_DIR`、`OCR_CACHE_DIR`、`OCR_DEBUG`、`MAX_BODY_MB` 可调
- 注意：后端会按请求抓取任意 URL（SSRF 面），非必要请把监听 IP 设为 `127.0.0.1` 或设置访问 token

> 所有后端统一支持：卡片「⚙ 配置」可改端口、token 与监听 IP；设置 token 后请求需带 `Authorization: Bearer <token>` 或 `X-Token: <token>`。

### redbag — 红包图片生成

FastAPI 后端，生成红包背景图（自定义金额、昵称、祝福语，随机背景），返回临时图片 URL（约 120 秒后自动清理）。

- 默认端口 3000（Python / FastAPI）
- 接口：`POST /send_redbag`，body `{user_id, user_name, amount, total, text?}`，返回 `{image_url}`（图片在 `/temp_images/<file>.png`）
- 依赖：`fastapi`、`Pillow`、`requests`、`uvicorn`
- 已接入 `ERROR_BACKEND_PORT` / `ERROR_BACKEND_HOST` / `ERROR_BACKEND_TOKEN`（token 非空时校验请求头）

### run_shell — Shell 命令执行

FastAPI 后端，执行 Shell 命令并把 stdout/stderr 渲染成图片返回 URL；支持长驻进程（create/check/del/list）。**仅支持 Linux**（依赖 `os.setsid` 进程组管理）。

- 默认端口 3011（Python / FastAPI）
- 接口（均需 token）：
  - `GET /run?token=<token>&cmd=<命令>`：执行命令（10 秒超时，强杀进程树），返回 `{output_url, error_url, retcode}`
  - `GET /create_process?token=<token>&cmd=<命令>`：创建长驻进程，返回 `{pid}`
  - `GET /check_process?token=<token>&pid=<pid>`：查看进程输出（渲染为图片）
  - `GET /del_process?token=<token>&pid=<pid>`：删除进程
  - `GET /list_process?token=<token>`：列出进程
- 依赖：`fastapi`、`Pillow`、`uvicorn`；字体（Sarasa Mono SC）随仓库提供
- token：`ERROR_BACKEND_TOKEN` 非空时优先使用（也兼容请求头 `X-Token` / `Authorization: Bearer`）；未配置时回退到内置 `123456`

### chart — 排行榜图表图片生成

FastAPI 后端，按排行榜数据（QQ 昵称 + 头像 + 数值）生成竖排图表图片，返回临时图片 URL（约 120 秒后自动清理）。

- 默认端口 3003（Python / FastAPI）
- 接口：`POST /chart`，body `{title, data: [{uid, un, value}, ...]}`（`uid` 为 `qq123456` 形式），返回 `{image_url}`（图片在 `/temp_images/<file>.png`）
- 依赖：`fastapi`、`Pillow`、`requests`、`uvicorn`
- 已接入 `ERROR_BACKEND_PORT` / `ERROR_BACKEND_HOST` / `ERROR_BACKEND_TOKEN`（token 非空时校验请求头）

## 新增后端约定

后端目录 = 仓库根目录下任意名称的目录，内含：

```text
<后端名>/
  backend.json         # 后端清单（见下）
  <入口脚本>           # 服务实现（Python / Node）
  requirements.txt     # Python 后端依赖（可选）
  package.json         # Node 后端依赖（可选）
```

`backend.json` 字段：

| 字段 | 说明 |
| --- | --- |
| `name` | 后端唯一名称（用于启停/日志/配置） |
| `description` | 卡片上的中文描述 |
| `type` | `python` 或 `node` |
| `entry` | 入口脚本文件名（相对后端目录） |
| `deps` | 依赖清单文件名（`requirements.txt` / `package.json`），缺省则跳过安装 |
| `port` | 默认端口 |

入口脚本必须读取 launcher 注入的环境变量：

- `ERROR_BACKEND_PORT`：监听端口（默认值应等于 `backend.json` 的 `port`）
- `ERROR_BACKEND_HOST`：监听 IP（默认 `0.0.0.0`）
- `ERROR_BACKEND_TOKEN`：访问 token（默认空）

token 非空时，后端应校验请求头 `Authorization: Bearer <token>` 或 `X-Token: <token>`，否则返回 401。参考已收录后端或常见框架模式（express 中间件、Flask / FastAPI 中间件、MCP 的 ASGI 包装）。

## 端口约定

本项目的 WebUI 监听地址与端口均为**首次运行随机生成**：地址默认 `0.0.0.0`，端口为随机五位数（10000-65535，自动避开已收录后端的端口），保存于 `.runtime.json`，之后保持稳定；`errorbackend webui-port` / `webui-host` 可查看或修改。带访问 token 鉴权。

新增后端选择默认端口时，避开本机已有服务端口，也不要与本项目已有后端重复。

## 目录结构

```text
launcher.py            入口：安装 WebUI 依赖并启动管理界面
webui.py               Web 管理界面（纯 Python 标准库）
errorbackend.py        命令行管理工具
install_cli.py         安装 errorbackend 命令到 PATH
assets/                WebUI 图标（当前为作者 GitHub 头像）
<后端目录>/            backend.json（类型/入口/依赖/默认端口）+ 服务代码
```

## 管理方式

管理全部通过 WebUI 完成：后端启停、依赖安装/删除、配置修改、运行日志都在页面里操作。端口/token/监听 IP 写入 `.runtime.json`（已 gitignore），启动时通过环境变量传给后端：`ERROR_BACKEND_PORT`、`ERROR_BACKEND_TOKEN`（非空时后端校验 `Authorization: Bearer <token>` 或 `X-Token: <token>`）、`ERROR_BACKEND_HOST`。

WebUI 自身同样有访问 token（首次运行自动生成）：页面先登录（记住一年），右上角「🔑 Token」可直接输入新 token 保存并立即生效，或 `errorbackend webui-token` 命令行修改；`webui-host` 修改监听地址，改完自动重启 WebUI。

右上角「🔄 重启 WebUI」可让管理界面重新加载后端清单（新增/修改后端、代码更新后无需手动重启进程）；命令行等价命令 `errorbackend webui-restart`。

## 命令行（errorbackend）

`errorbackend` 命令由 launcher 启动时自动安装（写入用户 PATH，Windows 会广播环境变更、Linux 写入 shell 配置；新打开的终端即可使用）。也可以手动安装：

```bash
python install_cli.py
```

```bash
errorbackend help [命令]                    # 查看帮助（如 errorbackend help start）
errorbackend list                           # 查看所有后端状态
errorbackend start --all                    # 后台启动全部（默认后台守护）
errorbackend start <后端名>                  # 后台启动单个
errorbackend start <后端名> --foreground     # 前台运行，Ctrl+C 停止
errorbackend stop --all                     # 停止全部
errorbackend restart <后端名>                # 重启
errorbackend logs <后端名> -f                # 查看/跟随日志
errorbackend info <后端名>                   # 进程详情（pid/时长/内存/拉起次数）
errorbackend monitor                        # 实时监控面板
errorbackend setup --all                    # 安装全部后端依赖
errorbackend del-deps <后端名>               # 删除单个后端依赖
errorbackend update                         # 从 Git 拉取项目更新（手动）
errorbackend webui                          # 后台启动 Web 管理界面（不占终端）
errorbackend webui-stop                     # 停止后台 WebUI
errorbackend webui-port 9000                # 查看/修改 WebUI 端口（修改后自动重启）
errorbackend webui-host 0.0.0.0             # 查看/修改 WebUI 监听地址（修改后自动重启）
errorbackend webui-token <token>            # 查看/修改 WebUI 访问 token（修改后自动重启）
errorbackend uninstall                      # 卸载 errorbackend 命令（删除命令与 PATH 配置）
errorbackend service-install                # [Linux] 注册 systemd 服务（开机自启 + 自动拉起）
errorbackend service-uninstall              # [Linux] 停止并移除 systemd 服务
```

命令行与 WebUI 共用同一套后端进程与状态（`logs/state.json`），可以混用。

## 来源与许可

本项目以 MIT License 发布，详见 [LICENSE](LICENSE)。`assets/` 图标为作者 GitHub 头像（error2913）。
