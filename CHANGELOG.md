# 更新日志

标题格式为 `## <版本号>`，release 工作流按标签版本号读取对应段落作为发布说明；日常更新以「Unreleased」汇总，发版前改成版本号并补日期。

## Unreleased

- 框架搭建：launcher / WebUI / CLI 管理机制（`errorbackend` 命令、`ERROR_BACKEND_*` 环境变量、systemd 服务 `error-backends-webui`）
- WebUI 空态提示：未收录后端时显示占位说明
- 默认 WebUI 端口改为 8911，避开其他后端生态常用端口（README「端口约定」）
- 收录首个后端 `ocr`（OCR 图片文字识别，Node + tesseract.js，默认端口 18699，与海豹插件默认配置一致），接入 token 鉴权与 `ERROR_BACKEND_*` 环境变量
- 无图形环境的 Linux 服务器启动 WebUI 时不再尝试打开浏览器（避免 xdg-open 报错），仅打印访问地址

## 0.1.0 - 2026-08-08

- 错误后端（error-backends）框架：launcher 后端发现/启停/依赖按需安装/进程守护
- WebUI 管理界面（纯 Python 标准库）：后端卡片、安装依赖日志、端口/token/监听 IP 配置、更新、日志查看
- 命令行工具 errorbackend：启停/日志/监控/依赖管理/更新，彩色 help
- Linux systemd 服务注册：开机自启 + 异常自动拉起 WebUI
- Git tag 自动打包 zip + tar.gz 并发布（GitHub Actions）
