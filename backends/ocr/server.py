# -*- coding: utf-8 -*-
"""OCR 后端：PP-OCRv6（ncnn 推理）+ Flask

与旧版 tesseract.js 后端保持同一套 HTTP 契约：
  GET  /health
  POST /api/ocr            body: {url 或 imageUrl, base64, mime, lang}
  POST /api/ocr/url
  POST /api/ocr/base64
由 error-backends launcher 注入 ERROR_BACKEND_PORT/_HOST/_TOKEN。
"""

from __future__ import annotations

import base64
import os
import shutil
import threading
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np
from flask import Flask, jsonify, request

from ppocr_ncnn import PaddleOCR

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "cache" / "models"

MIRROR_BASE = "https://mirrors.sdu.edu.cn/ncnn_modelzoo/liteocr/"
MODEL_FILES = [
    "PP-OCRv6_tiny_det.param",
    "PP-OCRv6_tiny_det.bin",
    "PP-OCRv6_small_rec.param",
    "PP-OCRv6_small_rec.bin",
    "PP-OCRv6_vocab.txt",
]

PORT = int(os.environ.get("ERROR_BACKEND_PORT") or os.environ.get("PORT") or 18699)
HOST = os.environ.get("ERROR_BACKEND_HOST") or os.environ.get("HOST") or "127.0.0.1"
TOKEN = os.environ.get("ERROR_BACKEND_TOKEN") or ""
MAX_BODY_MB = int(os.environ.get("MAX_BODY_MB") or "12")
MAX_IMAGE_BYTES = 20 * 1024 * 1024
UA = "Mozilla/5.0 (compatible; sealdice-ocr-backend/1.0)"

app = Flask(__name__)
app.json.ensure_ascii = False

_engine = None
_engine_lock = threading.Lock()
_stats = {"pending": 0, "total": 0}


class InputError(Exception):
    pass


def log(msg: str) -> None:
    print(f"[ocr] {msg}", flush=True)


# ---------------- 模型准备 ----------------

def ensure_models() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    missing = [f for f in MODEL_FILES if not (MODEL_DIR / f).exists()]
    if not missing:
        log(f"模型已就绪: {MODEL_DIR}")
        return
    log(f"模型缺失 {len(missing)} 个文件，开始从镜像下载…")
    for name in missing:
        dest = MODEL_DIR / name
        url = MIRROR_BASE + name
        tmp = dest.with_suffix(dest.suffix + ".part")
        log(f"下载 {name} …")
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=300) as resp, tmp.open("wb") as out:
            shutil.copyfileobj(resp, out)
        tmp.replace(dest)
        log(f"完成 {name} ({dest.stat().st_size} bytes)")
    log("模型下载完毕")


def load_engine() -> PaddleOCR:
    threads = max(1, min(8, int(os.environ.get("OCR_THREADS") or 2)))
    log(f"加载 PP-OCRv6 模型 (tiny_det + small_rec, threads={threads})…")
    t0 = time.time()
    eng = PaddleOCR(str(MODEL_DIR), num_threads=threads)
    log(f"引擎加载完成，耗时 {(time.time() - t0) * 1000:.0f}ms，词表 {len(eng.vocab)} 字符")
    return eng


def get_engine() -> PaddleOCR:
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = load_engine()
        return _engine


# ---------------- 图片获取 ----------------

def fetch_image_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise InputError("图片超过大小限制（20MB）")
    return data


def decode_image(data: bytes) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise InputError("无法解码图片（格式不支持或已损坏）")
    return img


def resolve_image(body: dict) -> np.ndarray:
    url = body.get("url") or body.get("imageUrl")
    b64 = body.get("base64")
    if b64:
        s = str(b64).strip()
        if s.startswith("data:"):
            s = s.split(",", 1)[1] if "," in s else s
        try:
            data = base64.b64decode(s, validate=False)
        except Exception as exc:
            raise InputError(f"base64 解码失败: {exc}") from exc
        if not data:
            raise InputError("base64 内容为空")
        return decode_image(data)
    if not url:
        raise InputError("缺少 url / base64 字段")
    data = fetch_image_bytes(str(url).strip())
    return decode_image(data)


# ---------------- OCR ----------------

def run_ocr(img: np.ndarray, lang: str | None) -> dict:
    eng = get_engine()
    with _engine_lock:
        _stats["pending"] += 1
        try:
            t0 = time.time()
            boxes = eng.ocr(img)
            duration = time.time() - t0
        finally:
            _stats["pending"] -= 1
            _stats["total"] += 1

    lines = [b.text for b in boxes if b.text]
    text = "\n".join(lines)
    confs = [b.conf for b in boxes if b.text]
    confidence = round((sum(confs) / len(confs) * 100), 1) if confs else 0.0
    return {
        "ok": True,
        "text": text,
        "confidence": confidence,
        "lang": lang or "zh+en+ja",
        "durationMs": round(duration * 1000),
        "engine": "PP-OCRv6 (ncnn)",
        "model": "tiny_det + small_rec",
        "lines": [{"text": b.text, "conf": round(b.conf * 100, 1)} for b in boxes if b.text],
    }


# ---------------- 路由 ----------------

@app.before_request
def auth():
    if TOKEN:
        authz = request.headers.get("Authorization") or ""
        if authz == f"Bearer {TOKEN}" or (request.headers.get("X-Token") or "") == TOKEN:
            return None
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    return None


@app.after_request
def cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    return resp


@app.get("/")
def index():
    return jsonify({
        "service": "sealdice-ocr-backend",
        "engine": "PP-OCRv6 (ncnn)",
        "endpoints": ["/health", "/api/ocr", "/api/ocr/url", "/api/ocr/base64"],
    })


@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "engine": "PP-OCRv6 (ncnn)",
        "workerLang": "zh+en+ja (multilingual)",
        "model": "PP-OCRv6 tiny_det + small_rec",
        "pendingJobs": _stats["pending"],
        "totalJobs": _stats["total"],
        "modelsReady": all((MODEL_DIR / f).exists() for f in MODEL_FILES),
    })


@app.post("/api/ocr")
def api_ocr():
    return _handle(request.get_json(silent=True) or {})


@app.post("/api/ocr/url")
def api_ocr_url():
    body = request.get_json(silent=True) or {}
    if not (body.get("url") or body.get("imageUrl")):
        return jsonify({"ok": False, "error": "缺少 url 字段"}), 400
    return _handle(body)


@app.post("/api/ocr/base64")
def api_ocr_base64():
    body = request.get_json(silent=True) or {}
    if not body.get("base64"):
        return jsonify({"ok": False, "error": "缺少 base64 字段"}), 400
    return _handle(body)


def _handle(body: dict):
    lang = body.get("lang")
    if not isinstance(lang, str) or not lang.strip():
        lang = None
    else:
        lang = lang.strip()
    try:
        img = resolve_image(body)
        result = run_ocr(img, lang)
        return jsonify(result)
    except InputError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(exc) or "OCR 识别失败"}), 500


@app.errorhandler(404)
def not_found(_):
    return jsonify({"ok": False, "error": "未知路径"}), 404


@app.errorhandler(413)
def too_large(_):
    return jsonify({"ok": False, "error": "请求体过大"}), 413


if __name__ == "__main__":
    ensure_models()
    log(f"启动 OCR 后端: http://{HOST}:{PORT}")
    app.run(host=HOST, port=PORT, threaded=True)
