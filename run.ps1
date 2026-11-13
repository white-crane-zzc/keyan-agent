# 运行方式（PowerShell）
# 1) 启动服务
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
# 2) 浏览器打开 http://127.0.0.1:8000

# 首次安装依赖（只需一次）
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install fastapi "uvicorn[standard]" python-multipart pymupdf numpy networkx httpx matplotlib pandas

# 配置模型（复制 .env.example 为 .env 后填 key；或指向本地 Ollama）
# Copy-Item .env.example .env
