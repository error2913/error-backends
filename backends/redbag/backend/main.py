# coding: utf-8

import os

# 以脚本所在目录为工作目录，保证 resources / fonts / temp_images 等相对路径正确
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import uvicorn

from config import TEMP_DIR
from routers import send_redbag, open_redbag, history

app = FastAPI()

TOKEN = os.environ.get("ERROR_BACKEND_TOKEN", "")


@app.middleware("http")
async def check_token(request, call_next):
    """error-backends 约定：ERROR_BACKEND_TOKEN 非空时校验 Authorization: Bearer <token> 或 X-Token: <token>"""
    if TOKEN:
        auth = request.headers.get("authorization", "")
        if auth == f"Bearer {TOKEN}" or (request.headers.get("x-token") or "") == TOKEN:
            return await call_next(request)
        return JSONResponse(status_code=401, content={"ok": False, "error": "unauthorized"})
    return await call_next(request)


# 挂载静态文件目录，用于提供临时图片访问
app.mount("/temp_images", StaticFiles(directory=TEMP_DIR), name="temp_images")

app.include_router(send_redbag.router)
app.include_router(open_redbag.router)
app.include_router(history.router)

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=os.environ.get("ERROR_BACKEND_HOST", "0.0.0.0"),
        port=int(os.environ.get("ERROR_BACKEND_PORT", "3000")),
    )
