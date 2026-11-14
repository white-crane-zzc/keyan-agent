"""全局配置：全部通过环境变量注入，密钥不进仓库。"""
from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PDF_DIR = DATA_DIR / "pdf"
PAGE_DIR = DATA_DIR / "pages"
PLOT_DIR = DATA_DIR / "plots"
DB_PATH = DATA_DIR / "library.db"
STATIC_DIR = ROOT / "static"

for _d in (DATA_DIR, PDF_DIR, PAGE_DIR, PLOT_DIR, STATIC_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def _load_dotenv() -> None:
    """零依赖读取项目根目录 .env（已存在的环境变量优先）。"""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        os.environ.setdefault(k, v)


_load_dotenv()

# ---- 大模型（OpenAI 兼容接口；也可指向本地 Ollama 的 /v1）----
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "").strip()
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
LLM_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "120"))

# 检索参数
CHUNK_MAX_CHARS = int(os.environ.get("CHUNK_MAX_CHARS", "900"))
TOP_K = int(os.environ.get("TOP_K", "8"))
DEDUPE_THRESHOLD = float(os.environ.get("DEDUPE_THRESHOLD", "0.90"))

# arXiv 抓取
ARXIV_API = "https://export.arxiv.org/api/query"
ARXIV_PDF = "https://arxiv.org/pdf/"


_PLACEHOLDER_HINTS = ("sk-xxx", "your-key", "sk-key")


def llm_ready() -> bool:
    """是否配置了大模型。本地 Ollama 不需要 key；模板占位文本不算配置。"""
    local = "localhost" in LLM_BASE_URL or "127.0.0.1" in LLM_BASE_URL
    key = LLM_API_KEY
    has_cjk = bool(re.search(r"[\u4e00-\u9fff]", key))   # 占位串里带中文，真 key 不会
    valid_key = bool(key) and len(key) >= 8 and not has_cjk \
        and not any(key.lower().startswith(h) for h in _PLACEHOLDER_HINTS)
    return valid_key or local
