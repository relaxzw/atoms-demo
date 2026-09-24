@echo off
chcp 65001 >nul
rem ============================================
rem  Atoms Demo 一键启动脚本（Windows）
rem  首次运行会自动创建虚拟环境并安装依赖
rem ============================================
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] 首次运行：创建虚拟环境 .venv ...
    python -m venv .venv
)

echo [2/3] 安装/更新依赖 ...
call ".venv\Scripts\activate.bat"
python -m pip install -r backend\requirements.txt -q

echo [3/3] 启动服务： http://localhost:8000
echo 提示：首次使用请先编辑 backend\.env 填入真实 DEEPSEEK_API_KEY
python backend\main.py

pause
