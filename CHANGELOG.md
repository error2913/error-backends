# 更新日志

标题格式为 `## <版本号>`，release 工作流按标签版本号读取对应段落作为发布说明；日常更新以「Unreleased」汇总，发版前改成版本号并补日期。

## 0.2.1 - 2026-08-14

- 修复卡片「⬆ 更新」点击后没有转圈反馈的问题：更新期间按钮显示「更新中」转圈，完成后恢复

## 0.2.0 - 2026-08-14

- 移植全部后端：新增 `image-url-to-base64`（图片 URL 转 base64，46678）、`mcp-files-exec`（MCP 文件与受限命令执行，3910）、`md-html-render`（Markdown/HTML 渲染为图片，37632）、`stream-output`（流式输出中转 SSE/轮询，3010）、`usage-chart`（token 用量图表，3009）、`web-read`（网页 URL 读取与截图，46799），全部接入 `ERROR_BACKEND_*` 环境变量与 token 鉴权
- 自定义配置支持 `{REPO_ROOT}` 模板与 `create_dir`：`backend.json` 的 `config` 默认值可写 `{REPO_ROOT}/...` 展开为仓库根目录；声明 `create_dir: true` 的路径在启动时自动创建（mcp-files-exec 沙箱工作目录默认 `data/mcp-files-exec`）
- 全新安装保留程序包自带 `backend.json` 的 `config` schema：安装/更新写回清单时以程序包自带清单为准、注册表仅兜底，自定义配置项不会因注册表缺字段而丢失
- 打包与更新排除 `data/`（后端运行数据目录，更新不覆盖、不删除）

## 0.1.0 - 2026-08-14

- 后端程序不再随仓库分发：主分支只保留框架与注册表信息（`backends.json`），一条指令安装只装框架；后端源码移到独立 `shop` 分支（release 打包与下载回退源），release 工作流新增从该分支暂存源码的步骤
- 注册表 `source` 与 `download_backend_files` 默认回退源改指向 `shop` 分支；点「安装」按注册表版本从 release 下载独立包，失败自动回退缓存/远端文件
- 安装改为按注册表版本从 GitHub release 独立包下载到 `installed/<name>`（缓存 `backends/<name>` 版本与注册表一致时直接复制），独立包缺失/失败自动回退缓存或远端文件；不再依赖商店缺文件补全
- 修复 Node 后端安装后指纹漂移：`npm install` 以安装后的实际依赖文件重算指纹，不再出现「装完仍显示安装按钮」或依赖反复重建
- 启动前先探测端口占用：端口已被未记录进程监听时跳过启动并明确提示；「启动全部 / 重启全部」与命令行 `start` 返回失败列表
- `logs/state.json` 改为原子写入（失败重试后兜底覆盖），避免异常退出留下半写文件
- 「安装全部」改为并行安装：同时触发所有未安装后端的安装，弹窗不再被互相覆盖，汇总提示失败项
- 框架更新改为 GitHub release 化：本体更新不再依赖 git——`update_project()` 查询 GitHub 最新 release（`_latest_release()`），tag 高于本地版本才下载 `error-backends-<版本>.zip` 解压覆盖仓库根目录（跳过 `installed/`、`logs/`、`backends/`、`dist/`、`.git/`、`.runtime.json`）；每个后端在 release 里有独立包（`error-backends-<名称>-<版本>.zip`）并各自版本控制，卡片「⬆ 更新」走 `update_backend(name)` 只下载对应后端包覆盖商店并重装依赖；打包改为本体 + 每后端独立包；版本检查对比 release tag 与远端 `backends.json` 注册表；升级清理仅 git 部署时执行
- ocr 后端引擎更换：tesseract.js → **PP-OCRv6 + ncnn**（tiny_det + small_rec，
  中英日多语），后端由 Node 改为 Python（Flask + ncnn + OpenCV + pyclipper），
   API 契约与端口（18699）保持不变；模型首次启动自动下载到 `ocr/cache/models/`
- 框架搭建：launcher / WebUI / CLI 管理机制（`errorbackend` 命令、`ERROR_BACKEND_*` 环境变量、systemd 服务 `error-backends-webui`）
- WebUI 空态提示：未收录后端时显示占位说明
- WebUI 端口改为首次运行随机生成五位数（10000-65535，避开已收录后端端口），不再固定端口，避免与本机其他服务冲突
- 收录首个后端 `ocr`（OCR 图片文字识别，Node + tesseract.js，默认端口 18699，与海豹插件默认配置一致），接入 token 鉴权与 `ERROR_BACKEND_*` 环境变量
- 自动开浏览器仅限 Windows；Linux/macOS 需显式设置 `BROWSER` 且存在图形环境才尝试（SSH -X 带 DISPLAY 也不会再误触发 xdg-open 报错）
- WebUI 默认监听 0.0.0.0，首次运行自动生成访问 token（`webui-token` 查看/修改、`webui-host` 改监听地址，改后自动重启）
- 新增 `errorbackend webui-host` / `webui-token` 命令；launcher 启动后台 WebUI 后即退出，不占用终端
- launcher 每次启动自动安装/刷新 `errorbackend` 命令行（幂等，Windows 广播 PATH 变更、Linux 写入 shell 配置且不重复追加）
- WebUI 启动自愈：检测到旧进程监听配置与当前不一致（host/port）时自动重启；后台子进程启动即崩溃时打印最近日志，避免“端口被旧进程占用”静默失败
- 文档不再提及任何其他项目/生态的端口号，端口避让改为通用约定
- WebUI 页面右上角新增「🔑 Token」管理弹窗：可查看/修改/随机生成 WebUI token（立即生效），替代原浏览器 prompt 弹框
- WebUI 改为 token 登录页：打开只显示 token 输入框，登录后浏览器记住一年；Token 弹窗简化为直接输入新 token 保存生效
- WebUI 右上角新增「🔄 重启 WebUI」按钮（等价 `errorbackend webui-restart`）：重启后重新加载后端清单，新增/修改后端或代码更新后无需手动重启进程
- 修复「⬆ 更新」按钮未携带 WebUI token 导致 401（unauthorized）的问题，改用统一 api() 请求
- 收录 `redbag`（红包图片生成，FastAPI，3000）与 `run_shell`（Shell 执行并渲染图片，仅 Linux，3011）两个后端，接入 `ERROR_BACKEND_*` 环境变量与 token 鉴权，资源路径改为脚本目录相对
- 收录 `chart` 后端（排行榜图表图片生成，FastAPI，3003）；后端目录统一改名为 ASCII 路径（`redbag/backend`、`run_shell/backend`、`chart`），不再出现中文路径
- WebUI：「⬆ 更新」点击后转圈、更新成功自动重启 WebUI；后端卡片按依赖是否就绪排序；新增「🙈 隐藏未装依赖」开关（状态本地记住）
- WebUI 后端卡片新增「重启」按钮（依赖已装且运行中时显示），接口 `POST /api/restart/<name>`
- 更新后自动重启全部后端；后端卡片展示版本号，对比 GitHub release 与远端注册表版本（60 秒缓存），有新版时更新按钮显示小红点、卡片出现「⬆ 更新」按钮（下载独立包+检查依赖+重启）；新增「删除」按钮（程序与依赖一起删除，商店源文件不动）
- 更新日志弹窗改为排版化的版本/条目展示
- 修复 WebUI 后台安装依赖（pip/npm）时子进程未带 `CREATE_NO_WINDOW` 导致 Windows 弹黑框的问题，所有后台子进程调用点补齐
- 改为独立分发模式：后端程序按需下载到 `backends/`，依赖随安装/卸载/更新自动管理，移除手动装/卸依赖入口；README 改为纯索引，后端介绍移入各包目录
- 依赖精确同步：安装/更新后按依赖清单重建环境（Python 清单变化重建 venv，Node 用 `npm ci` 按 lockfile），确保依赖不多不少后再启动；整体更新改为“先停 → 同步依赖 → 再启动”
- 修复 PAGE 内 JS 的 `split('\n')` 反斜杠被 Python 转义成真实换行导致登录页脚本失效（`login is not defined`）的问题
- 卡片按钮状态机：未安装仅「安装」，安装中转圈+日志，安装后「启动/配置/日志/卸载」，运行中「停止/重启/配置/日志/卸载」；主题按钮移到右下角；「隐藏未装依赖」改名「隐藏未装后端」
- 自定义后端配置：`backend.json` 的 `config` 声明 schema，配置弹窗动态渲染，保存后以环境变量注入后端（ocr 示例：`MAX_BODY_MB`、`OCR_THREADS`）
- 改为“商店 + 运行目录”模型：`backends/` 为 git 商店永不删除，安装复制到 `installed/`（gitignore），卸载只删 `installed/<name>`；已安装 = 程序 + 依赖都就绪；安装/卸载均为异步转圈 + 日志；未安装卡片不展示运行时长/拉起次数；pip 失败自动重试一次
- 升级自动清理：launcher 启动时删除旧版顶层后端残留目录（仅限 git 已不跟踪的 `ocr` / `redbag` / `run_shell` / `chart` 旧目录）

## 0.1.0 - 2026-08-08

- 错误后端（error-backends）框架：launcher 后端发现/启停/依赖按需安装/进程守护
- WebUI 管理界面（纯 Python 标准库）：后端卡片、安装依赖日志、端口/token/监听 IP 配置、更新、日志查看
- 命令行工具 errorbackend：启停/日志/监控/依赖管理/更新，彩色 help
- Linux systemd 服务注册：开机自启 + 异常自动拉起 WebUI
- Git tag 自动打包 zip + tar.gz 并发布（GitHub Actions）
