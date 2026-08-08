# 更新日志

标题格式为 `## <版本号>`，release 工作流按标签版本号读取对应段落作为发布说明；日常更新以「Unreleased」汇总，发版前改成版本号并补日期。

## Unreleased

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

## 0.1.0 - 2026-08-08

- 错误后端（error-backends）框架：launcher 后端发现/启停/依赖按需安装/进程守护
- WebUI 管理界面（纯 Python 标准库）：后端卡片、安装依赖日志、端口/token/监听 IP 配置、更新、日志查看
- 命令行工具 errorbackend：启停/日志/监控/依赖管理/更新，彩色 help
- Linux systemd 服务注册：开机自启 + 异常自动拉起 WebUI
- Git tag 自动打包 zip + tar.gz 并发布（GitHub Actions）
