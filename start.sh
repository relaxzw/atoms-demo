#!/usr/bin/env bash
# ============================================
#  Atoms Demo 一键启动脚本（macOS / Linux）
#  首次运行会自动创建虚拟环境并安装依赖
# ============================================
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "[1/3] 首次运行：创建虚拟环境 .venv ..."
  python3 -m venv .venv
fi

echo "[2/3] 安装/更新依赖 ..."
source .venv/bin/activate
python -m pip install -r backend/requirements.txt -q

echo "[3/3] 启动服务： http://localhost:8000"
echo "提示：首次使用请先编辑 backend/.env 填入真实 DEEPSEEK_API_KEY"
python backend/main.py
