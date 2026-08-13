# ocr 后端

OCR 图片文字识别后端，供海豹插件 `sealdice-OCR-plugin` 调用，也暴露标准 HTTP API
供其他程序使用。

## 引擎

- 推理框架：**ncnn**（CPU，无 GPU 依赖，适合 2 核 2G 小服务器）
- 检测模型：**PP-OCRv6 tiny_det**（语言无关，约 1.9MB）
- 识别模型：**PP-OCRv6 small_rec**（多语词表 18708 字符，覆盖中文 / 英文 / 日语，
  约 21MB）
- 说明：PP-OCRv6 的 tiny_rec 词表不含日文假名，无法识别日语；因此识别用
  small_rec（tiny 档仅用于检测），在精度与 2G 内存之间取平衡。

模型文件首次启动时自动从镜像
`https://mirrors.sdu.edu.cn/ncnn_modelzoo/liteocr/` 下载到 `cache/models/`
（已 gitignore，不进仓库 / 发布包）。

## API

- `GET /health`：健康检查，返回引擎 / 已加载语言 / 队列任务数等
- `POST /api/ocr`：`{url 或 imageUrl, base64, mime, lang}`（与旧版一致）
- `POST /api/ocr/url`：`{url, lang}`
- `POST /api/ocr/base64`：`{base64, mime, lang}`

响应：

```json
{
  "ok": true,
  "text": "识别出的文字，多行用 \\n 连接",
  "confidence": 98.7,
  "lang": "zh+en+ja",
  "durationMs": 123,
  "engine": "PP-OCRv6 (ncnn)",
  "model": "tiny_det + small_rec"
}
```

鉴权：launcher 注入 `ERROR_BACKEND_TOKEN` 时，请求头需带
`Authorization: Bearer <token>` 或 `X-Token: <token>`。

## 本地运行

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt   # Windows: .venv\Scripts\pip
ERROR_BACKEND_PORT=18699 python server.py
```
