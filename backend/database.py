"""
database.py —— SQLite 数据持久化层
保存生成的 AI 应用项目（名称、描述、HTML 代码、创建时间）
使用 Python 标准库 sqlite3，零额外依赖，Windows 下开箱即用。
"""
import os
import sqlite3
import time
from pathlib import Path

# 数据库文件放在 backend 目录下（与源码同目录，部署时持久化卷挂载此目录即可）
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.environ.get("ATOMS_DB_PATH", str(BASE_DIR / "atoms.db"))


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """建表（幂等）"""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL DEFAULT '未命名应用',
                description TEXT NOT NULL DEFAULT '',
                prompt TEXT NOT NULL DEFAULT '',
                html_code TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        conn.commit()


def create_project(name: str, description: str, prompt: str, html_code: str) -> dict:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO projects (name, description, prompt, html_code, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, description, prompt, html_code, time.time()),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def update_project(project_id: int, name: str, description: str, html_code: str) -> dict | None:
    with _connect() as conn:
        conn.execute(
            "UPDATE projects SET name = ?, description = ?, html_code = ? WHERE id = ?",
            (name, description, html_code, project_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return dict(row) if row else None


def get_project(project_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return dict(row) if row else None


def list_projects(limit: int = 50) -> list[dict]:
    """按创建时间倒序返回历史项目"""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM projects ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def delete_project(project_id: int) -> bool:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.commit()
    return cur.rowcount > 0


def rename_project(project_id: int, name: str) -> dict | None:
    with _connect() as conn:
        conn.execute("UPDATE projects SET name = ? WHERE id = ?", (name, project_id))
        conn.commit()
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return dict(row) if row else None
