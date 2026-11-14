@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [1/2] 首次运行，正在创建虚拟环境...
  python -m venv .venv
  ".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
)
if not exist ".env" (
  echo 提示：还没有 .env，问答/翻译将只返回检索证据。复制 .env.example 为 .env 并填 key 后重启即可启用大模型。
)
echo [2/2] 启动服务： http://127.0.0.1:8000
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
endlocal
