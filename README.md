# error-backends（错误后端）

海豹插件配套的后端管理框架：一个 launcher 统一管理若干**独立分发**的 HTTP 后端服务，提供 WebUI 管理界面、命令行工具（`errorbackend`）、按需下载安装、进程守护与版本更新。

后端程序独立分发：一条指令安装（git clone + `python launcher.py`）只装框架与后端注册表索引（[backends.json](backends.json)），**不含后端程序**；后端源码在独立 `shop` 分支（release 打包与下载回退用），每个后端在 release 中有独立包、各自版本控制。点「安装」才下载程序：缓存 `backends/<name>` 版本与注册表一致时直接复制，否则按注册表版本从 GitHub release 下载独立包到运行目录 `installed/<name>/`（gitignore），失败自动回退缓存/远端文件；依赖随**安装 / 卸载 / 更新**生命周期自动处理，不提供手动装/卸依赖的入口。初始状态 `installed/` 为空，WebUI 只展示后端资料卡片与「安装」按钮。

## 快速开始

环境要求：Python 3.9+；Node.js 20+（当安装的 Node 后端需要时）。

```bash
git clone https://github.com/error2913/error-backends.git && cd error-backends && python launcher.py
```

一条命令搞定全部：首次运行自动安装所需依赖、随机生成 WebUI 端口与访问 token，并后台启动管理界面（命令执行完即退出）。启动输出会打印访问地址与 token（端口为随机五位数 10000-65535）。launcher 每次启动自动安装/刷新 `errorbackend` 命令行；自动开浏览器仅限 Windows（Linux/macOS 需显式设置 `BROWSER`）。

## 后端索引

| 名称 | 描述 | 类型 | 默认端口 | 版本 |
| --- | --- | --- | --- | --- |
| `ocr` | OCR 图片文字识别（PP-OCRv6 + ncnn，中英日多语，支持 URL / base64） | python | 18699 | 1.0.0 |
| `redbag` | 红包图片生成（FastAPI，自定义金额/祝福语/随机背景） | python | 3000 | 1.0.0 |
| `run_shell` | 执行 Shell 命令并将输出渲染为图片（仅 Linux） | python | 3011 | 1.1.1 |
| `chart` | 排行榜图表图片生成（FastAPI，头像 + 排名列表） | python | 3003 | 1.0.0 |
| `image-url-to-base64` | 图片 URL 转 base64（自动识别格式，静态 GIF 转 PNG） | python | 46678 | 1.0.0 |
| `mcp-files-exec` | MCP：AI 读写文件与执行受限命令（沙箱 + 命令拦截 + 审计日志） | python | 3910 | 1.0.1 |
| `md-html-render` | Markdown/HTML 渲染为图片（MCP，支持 LaTeX 与多主题） | node | 37632 | 1.0.0 |
| `stream-output` | 流式输出中转（SSE 分块/轮询） | python | 3010 | 1.0.0 |
| `usage-chart` | token 用量图表（年/月视图） | python | 3009 | 1.0.0 |
| `web-read` | 网页 URL 内容读取与截图（MCP） | node | 46799 | 1.0.0 |

> 本 README 只做索引；每个后端的详细说明见 `shop` 分支的 `backends/<name>/README.md`（若存在）。

## 使用方式

- **安装**：WebUI 卡片「安装」或 `errorbackend install-backend <name>`——按注册表版本从 release 下载独立包到 `installed/<name>` 并自动安装依赖（缓存版本一致时直接复制；独立包失败自动回退缓存/远端文件；选择式下载，未选择的后端不出现在运行环境），完成后可启动
- **启停 / 重启**：卡片按钮或 `errorbackend start / stop / restart <name>`
- **更新**：右上角「⬆ 更新」下载最新 release 覆盖本体并重启全部后端与 WebUI；卡片「⬆ 更新」单独更新该后端（下载独立包覆盖商店 + 重装依赖 + 重启）；后台 60 秒检查一次远端版本，有新版时更新按钮出现小红点
- **卸载**：卡片「卸载」（卸载中转圈 + 日志）或 `errorbackend uninstall-backend <name>`——停止并删除 `installed/<name>`（程序 + 依赖），**下载缓存与 git 商店里的包不受影响**

依赖随以上操作自动管理，无手动「安装依赖 / 删除依赖」按钮。

卡片按钮按状态切换：未安装只显示「安装」；安装中显示转圈 + 「日志」；安装完成后显示「启动 / 配置 / 日志 / 卸载」；运行中显示「停止 / 重启 / 配置 / 日志 / 卸载」。「配置」弹窗除端口/token/监听 IP 外，还会按后端 `backend.json` 的 `config` 声明渲染自定义配置项（保存后重启后端生效）。

## 跨平台

- Python 后端用独立 venv（Windows `.venv\Scripts\python.exe`，Linux `.venv/bin/python`），Node 后端用 `node_modules`；依赖只在安装/更新时处理
- 后台守护：Windows `DETACHED_PROCESS`（不弹黑框），Linux `start_new_session`；后台子进程统一带 `CREATE_NO_WINDOW`
- 安装 `errorbackend`：Windows 生成 `errorbackend.cmd`，Linux 写入 shell 配置（`.bashrc` / `.zshrc` / `.profile`）

## Linux 系统服务

```bash
python launcher.py service-install      # 注册并立即启动（需 root/sudo）
python launcher.py service-uninstall    # 停止并移除服务
```

日志：`journalctl -u error-backends-webui -f`。

## 端口约定

WebUI 监听地址与端口均为首次运行随机生成（地址默认 `0.0.0.0`，端口 10000-65535，避开已收录后端的端口），保存于 `.runtime.json`；`errorbackend webui-port` / `webui-host` 可改。新增后端默认端口避开本机已有服务端口，也不与已收录后端重复。

## 目录结构

```text
launcher.py            入口：WebUI 启停/后端管理/依赖/更新/打包/systemd
webui.py               Web 管理界面（纯 Python 标准库）
errorbackend.py        命令行管理工具
install_cli.py         安装 errorbackend 命令到 PATH
backends.json          后端注册表索引（名称/介绍/版本/下载源/文件清单）
backends/<name>/       后端程序缓存（点安装/更新时下载解压到这里，gitignore；源码在独立 shop 分支）
installed/<name>/      已安装后端运行目录（gitignore，安装时下载/复制程序，卸载即删）
data/                  后端数据目录（如 mcp-files-exec 沙箱根目录，gitignore）
assets/                WebUI 图标
```

## 管理方式

全部通过 WebUI 完成：后端安装/卸载、启停、更新、日志、端口/token/监听 IP 配置。`.runtime.json` 保存运行时配置（已 gitignore）。页面右上角：「🔑 Token」管理访问 token、「⬆ 更新」整体更新、「🔄 重启 WebUI」重新加载后端清单、「🙈 隐藏未安装」只显示已装后端。

## 更新

- **本体更新**：WebUI 右上角「⬆ 更新」或 `errorbackend update`。检测 GitHub 最新 release（`error-backends-<版本>.zip`），比本地版本新就下载并直接覆盖仓库文件，不依赖 git——本地文件有改动也不会阻塞更新；更新成功后自动重启 WebUI 使新代码生效。
- **后端更新**：每个后端在 release 里有独立包（`error-backends-<后端名>-<版本>.zip`），版本各自独立记录在 `backends.json`。注册表版本高于本地版本时，卡片出现「⬆ 更新」按钮，点击只下载对应后端独立包覆盖缓存并重装程序与依赖，不影响其他后端；或 `uninstall-backend` 后重新 `install-backend`。
- **升级残留**：旧版（后端位于仓库顶层）升级到商店模型后，顶层目录里的 `node_modules/`、`.venv/`、缓存等未跟踪残留会自动清理——仅 git 部署时 launcher 启动会检测并整目录删除「git 已不再跟踪」的旧后端目录（`ocr` / `redbag` / `run_shell` / `chart`），商店 `backends/`、`installed/`、`logs/` 与运行配置不受影响。

## 命令行（errorbackend）

由 launcher 启动时自动安装，或手动 `python install_cli.py`：

```text
errorbackend help                          查看帮助
errorbackend list                          查看所有后端状态
errorbackend install-backend <name>        安装后端（下载程序 + 安装依赖）
errorbackend uninstall-backend <name>      卸载后端（停止并删除程序与依赖）
errorbackend start/stop/restart <name>     启停/重启
errorbackend update                        从 GitHub 更新到最新版
errorbackend webui / webui-stop / webui-restart / webui-port / webui-host / webui-token
```

## 新增后端（shop 分支源码 + main 注册表）

1. 在 `shop` 分支的 `backends/<name>/` 放置程序文件，含 `backend.json`（`name` / `description` / `type` / `entry` / `deps` / `port` / `version`）
2. 在 main 分支根目录 `backends.json` 注册表中添加条目：
   - `source`：程序文件下载根地址（默认 `https://raw.githubusercontent.com/error2913/error-backends/shop/backends/<name>`）
   - `files`：需下载的文件清单（相对路径，须与包目录保持一致）
   - `config`（可选）：自定义配置 schema，`{key: {label, type: text|number, default, env}}`——WebUI 配置弹窗渲染，保存后经 launcher 以环境变量 `env` 注入后端进程
3. 后端源码改动提交到 `shop` 分支、注册表版本等元数据同步到 main 的 `backends.json`；发布 release 后 WebUI 即出现该后端卡片，可「安装」

## 来源与许可

本项目以 MIT License 发布，详见 [LICENSE](LICENSE)；`assets/` 图标为作者 GitHub 头像（error2913）。
