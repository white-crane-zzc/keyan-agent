"""大模型连通性自检：python tests/check_llm.py
会打印当前配置（key 只显示首尾），并发一次极小请求验证是否可用。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, llm  # noqa: E402


def mask(k: str) -> str:
    if not k:
        return "(空)"
    return k[:6] + "…" + k[-4:] if len(k) > 12 else "(已填)"


print("BASE_URL :", config.LLM_BASE_URL)
print("API_KEY  :", mask(config.LLM_API_KEY))
print("MODEL    :", config.LLM_MODEL)
print("llm_ready:", config.llm_ready())

if not config.llm_ready():
    print("\n结论：还没配置好。把 .env 里的 LLM_API_KEY 换成真实 key（或指向本地 Ollama）后重启服务。")
    sys.exit(2)

try:
    out = llm.chat([{"role": "user", "content": "只回答两个字：通了"}], max_tokens=16)
    print("\n返回:", (out or "").strip()[:120])
    print("结论：大模型可用。")
except Exception as e:
    print("\n调用失败:", type(e).__name__, str(e)[:300])
    print("结论：连不上。检查 key、base_url、模型名，或网络是否可达该服务商。")
    sys.exit(1)
