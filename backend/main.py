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
import hashlib
import os
import re
import secrets
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
import auth
import database

# ---------- 业务配置（可 .env 覆盖） ----------
SUPPORT_PHONE = os.environ.get("SUPPORT_PHONE", "15872398796")
DEFAULT_TOKEN_LIMIT = int(os.environ.get("DEFAULT_TOKEN_LIMIT", "100000"))
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "123456")


def _ensure_admin() -> None:
    """启动时确保预设管理员账号存在（用户名/密码由 .env 配置）"""
    if database.get_user_by_username(ADMIN_USERNAME) is None:
        sha = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()
        database.create_user(ADMIN_USERNAME, auth.hash_password(sha), DEFAULT_TOKEN_LIMIT, is_admin=1)

# ---------- 登录会话（内存 token → 用户） ----------
_sessions: dict[str, dict] = {}
_SESSION_TTL = 86400  # 24 小时


def _auth_user(token: str) -> dict | None:
    """校验登录 token，返回用户或 None"""
    s = _sessions.get(token)
    if not s or s["expires"] < time.time():
        return None
    return database.get_user_by_username(s["username"])


# ---------- 初始化 ----------
database.init_db()
_ensure_admin()

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
    token: str | None = Field(default=None, description="登录令牌，用于识别用户并扣减 Token 余额")


class RenameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=30, description="新的项目名称")


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30, description="用户名")
    password_hash: str = Field(..., min_length=64, max_length=64, description="前端 SHA-256 后的密码（hex）")


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=30, description="用户名")
    password_hash: str = Field(..., min_length=64, max_length=64, description="前端 SHA-256 后的密码（hex）")
    captcha: str = Field(..., min_length=1, max_length=8, description="图形验证码")
    captcha_token: str = Field(..., min_length=1, description="验证码令牌")


class ChangePasswordRequest(BaseModel):
    token: str = Field(..., min_length=1, description="登录令牌")
    old_password_hash: str = Field(..., min_length=64, max_length=64, description="原密码 SHA-256（hex）")
    new_password_hash: str = Field(..., min_length=64, max_length=64, description="新密码 SHA-256（hex）")


class GenerateResponse(BaseModel):
    id: int
    name: str
    description: str
    prompt: str
    html_code: str
    created_at: float
    used_tokens: int = 0
    remaining_tokens: int = 0


# ---------- API 路由 ----------
@app.post("/api/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):
    """核心流程：鉴权 → 余额检查 → DeepSeek 生成 → 扣减 Token → 保存"""
    if _rate_limited():
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试。")

    # 登录鉴权
    user = _auth_user(req.token or "")
    if user is None:
        raise HTTPException(status_code=401, detail="请先登录后再生成应用")

    # Token 余额检查（不足则提前告知，无法执行）
    if user["token_balance"] <= 0:
        raise HTTPException(status_code=402, detail=f"Token 余额不足，无法执行本轮生成，请联系服务商：{SUPPORT_PHONE}")

    # 模式一：基于现有项目按指令修改（对话式迭代）
    if req.instruction and req.project_id:
        existing = database.get_project(req.project_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        try:
            result = ai_builder.modify_app(req.instruction, existing["html_code"])
        except ai_builder.AIBuilderError as e:
            raise HTTPException(status_code=502, detail=str(e))
        resp = database.update_project(req.project_id, existing["name"], existing["description"], result["html_code"])
    else:
        # 模式二：全新生成 / 原需求重新生成（覆盖）
        try:
            result = ai_builder.generate_app(req.prompt)
        except ai_builder.AIBuilderError as e:
            raise HTTPException(status_code=502, detail=str(e))
        if req.project_id:
            updated = database.update_project(req.project_id, result["name"], result["description"], result["html_code"])
            if updated is None:
                raise HTTPException(status_code=404, detail="项目不存在")
            resp = updated
        else:
            resp = database.create_project(result["name"], result["description"], req.prompt, result["html_code"])

    # 扣减用户 Token 余额
    used = result.get("used_tokens", 0)
    new_balance = max(0, user["token_balance"] - used)
    database.update_token_balance(user["id"], new_balance)

    resp["used_tokens"] = used
    resp["remaining_tokens"] = new_balance
    return resp


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


# ---------- 验证码存储（内存，带过期） ----------
_captcha_store: dict[str, dict] = {}
_CAPTCHA_TTL = 300  # 秒


def _clean_captcha_store() -> None:
    now = time.time()
    for k in [k for k, v in _captcha_store.items() if v["expires"] < now]:
        _captcha_store.pop(k, None)


# ---------- 认证 API ----------
@app.get("/api/captcha")
def get_captcha():
    """生成图形验证码，返回 SVG 与一次性令牌"""
    svg, code = auth.generate_captcha()
    token = secrets.token_hex(16)
    _captcha_store[token] = {"code": code, "expires": time.time() + _CAPTCHA_TTL}
    _clean_captcha_store()
    return {"token": token, "svg": svg}


@app.post("/api/register")
def register(req: RegisterRequest):
    """注册：用户名唯一 + 密码散列存储"""
    username = req.username.strip()
    if not re.fullmatch(r"[a-zA-Z0-9_]{3,30}", username):
        raise HTTPException(status_code=400, detail="用户名仅支持字母、数字、下划线，3-30 位")
    if not re.fullmatch(r"[0-9a-f]{64}", req.password_hash):
        raise HTTPException(status_code=400, detail="密码格式不正确")
    if database.get_user_by_username(username):
        raise HTTPException(status_code=409, detail="用户名已存在")
    stored = auth.hash_password(req.password_hash)
    is_admin = 1 if username == ADMIN_USERNAME else 0
    user = database.create_user(username, stored, DEFAULT_TOKEN_LIMIT, is_admin=is_admin)
    if user is None:
        raise HTTPException(status_code=409, detail="用户名已存在")
    return {"ok": True, "username": user["username"], "token_balance": user["token_balance"], "is_admin": user["is_admin"]}


@app.post("/api/login")
def login(req: LoginRequest):
    """登录：验证码校验 + 密码校验"""
    entry = _captcha_store.pop(req.captcha_token, None)
    if entry is None or entry["expires"] < time.time():
        raise HTTPException(status_code=400, detail="验证码已过期，请点击刷新")
    if entry["code"].lower() != req.captcha.strip().lower():
        raise HTTPException(status_code=400, detail="验证码错误")
    user = database.get_user_by_username(req.username.strip())
    if user is None or not auth.verify_password(req.password_hash, user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if user["status"] == "disabled":
        raise HTTPException(status_code=403, detail=f"用户已禁用，请联系 {SUPPORT_PHONE}")
    token = secrets.token_hex(32)
    _sessions[token] = {"username": user["username"], "expires": time.time() + _SESSION_TTL}
    return {"ok": True, "token": token, "username": user["username"], "token_balance": user["token_balance"], "is_admin": user["is_admin"]}


@app.get("/api/me")
def me(token: str):
    """查询当前登录用户的 Token 余额"""
    user = _auth_user(token)
    if user is None:
        raise HTTPException(status_code=401, detail="请先登录")
    return {"username": user["username"], "token_balance": user["token_balance"], "is_admin": user["is_admin"]}


@app.post("/api/change-password")
def change_password(req: ChangePasswordRequest):
    """修改当前用户密码"""
    user = _auth_user(req.token)
    if user is None:
        raise HTTPException(status_code=401, detail="请先登录")
    if not auth.verify_password(req.old_password_hash, user["password_hash"]):
        raise HTTPException(status_code=400, detail="原密码错误")
    if not re.fullmatch(r"[0-9a-f]{64}", req.new_password_hash):
        raise HTTPException(status_code=400, detail="新密码格式不正确")
    database.update_password(user["id"], auth.hash_password(req.new_password_hash))
    return {"ok": True}


def _auth_admin(token: str) -> dict | None:
    """校验管理员 token，返回管理员用户或 None"""
    user = _auth_user(token)
    if user is None or not user.get("is_admin"):
        return None
    return user


# ---------- 管理后台 API（仅管理员） ----------
@app.get("/api/admin/users")
def admin_list_users(token: str):
    if _auth_admin(token) is None:
        raise HTTPException(status_code=403, detail="无管理员权限")
    return database.list_users()


@app.post("/api/admin/users/{user_id}/disable")
def admin_disable_user(user_id: int, token: str):
    if _auth_admin(token) is None:
        raise HTTPException(status_code=403, detail="无管理员权限")
    target = database.get_user_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target["is_admin"]:
        raise HTTPException(status_code=400, detail="不能禁用管理员账号")
    return database.set_user_status(user_id, "disabled")


@app.post("/api/admin/users/{user_id}/enable")
def admin_enable_user(user_id: int, token: str):
    if _auth_admin(token) is None:
        raise HTTPException(status_code=403, detail="无管理员权限")
    u = database.set_user_status(user_id, "active")
    if u is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return u


@app.delete("/api/admin/users/{user_id}")
def admin_delete_user(user_id: int, token: str):
    if _auth_admin(token) is None:
        raise HTTPException(status_code=403, detail="无管理员权限")
    target = database.get_user_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target["is_admin"]:
        raise HTTPException(status_code=400, detail="不能删除管理员账号")
    database.delete_user(user_id)
    return {"ok": True}


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
