"""
main.py —— Atoms Demo 后端入口（FastAPI）

启动方式（在项目根目录）：
    pip install -r backend/requirements.txt
    python backend/main.py
然后浏览器打开 http://localhost:8000

服务两个职责：
1. 提供 /api/* 接口：AI 生成应用、历史项目持久化（SQLite）
2. 伺服 frontend/ 下的静态前端，前后端一体，单进程运行
"""
import os
import time
from collections import deque
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# ---------- 加载环境变量（必须在 import ai_builder / database 之前！）----------
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
load_dotenv(BACKEND_DIR / ".env")

import ai_builder
import database

# ---------- 初始化 ----------
database.init_db()

# 简单内存限流：限制每分钟生成请求数，防止公网部署时被刷接口消耗 DeepSeek 额度
_RATE_WINDOW = 60.0
_RATE_LIMIT = 20
_recent_requests = deque()


def _rate_limited() -> bool:
    now = time.time()
    while _recent_requests and _recent_requests[0] < now - _RATE_WINDOW:
        _recent_requests.popleft()
    if len(_recent_requests) >= _RATE_LIMIT:
        return True
    _recent_requests.append(now)
    return False


app = FastAPI(title="Atoms Demo", version="1.0.0")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """兑底：未捕获异常统一返回 JSON，避免前端拿到 HTML 错误页"""
    return JSONResponse(status_code=500, content={"detail": f"服务器内部错误：{exc}"})


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """基础安全加固：防 MIME 嗅探 / 防点击劫持 / 控制 Referrer 泄露"""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ---------- API 模型 ----------
class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=2, max_length=2000, description="用户描述想构建的应用")
    project_id: int | None = Field(default=None, description="传入则在该项目上迭代更新")
    instruction: str | None = Field(default=None, max_length=1000, description="传入则在现有代码基础上按指令修改")


class RenameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=30, description="新的项目名称")


class GenerateResponse(BaseModel):
    id: int
    name: str
    description: str
    prompt: str
    html_code: str
    created_at: float


# ---------- API 路由 ----------
@app.post("/api/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):
    """核心流程：需求 → DeepSeek 生成 → 保存（或迭代更新）"""
    if _rate_limited():
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试。")

    # 模式一：基于现有项目按指令修改（对话式迭代）
    if req.instruction and req.project_id:
        existing = database.get_project(req.project_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        try:
            result = ai_builder.modify_app(req.instruction, existing["html_code"])
        except ai_builder.AIBuilderError as e:
            raise HTTPException(status_code=502, detail=str(e))
        # 修改模式保留原名称与简介，只更新代码
        return database.update_project(req.project_id, existing["name"], existing["description"], result["html_code"])

    # 模式二：全新生成 / 原需求重新生成（覆盖）
    try:
        result = ai_builder.generate_app(req.prompt)
    except ai_builder.AIBuilderError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if req.project_id:
        updated = database.update_project(req.project_id, result["name"], result["description"], result["html_code"])
        if updated is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        return updated
    return database.create_project(result["name"], result["description"], req.prompt, result["html_code"])


@app.get("/api/projects")
def list_projects():
    """历史项目列表（不含完整代码，减少传输）"""
    items = database.list_projects()
    for it in items:
        it.pop("html_code", None)
    return items


@app.get("/api/projects/{project_id}")
def get_project(project_id: int):
    item = database.get_project(project_id)
    if item is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return item


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: int):
    ok = database.delete_project(project_id)
    if not ok:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"ok": True}


@app.patch("/api/projects/{project_id}")
def rename_project(project_id: int, req: RenameRequest):
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="名称不能为空")
    updated = database.rename_project(project_id, name)
    if updated is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return updated


# ---------- 静态前端（必须放在 API 路由之后挂载） ----------
FRONTEND_DIR = PROJECT_ROOT / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


# ---------- 本地启动入口 ----------
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    print(f"Atoms Demo 已启动： http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
