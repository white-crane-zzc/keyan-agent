"""大模型接入层：OpenAI 兼容协议（云端 API 或本地 Ollama 的 /v1 均可）。"""
from __future__ import annotations

import re

import httpx

from .config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_TIMEOUT, llm_ready

SYSTEM = (
    "你是严谨的科研助手。回答必须基于给定材料，不得编造；"
    "引用材料时用 [1][2] 这样的编号标注来源，编号必须来自材料。"
    "材料不足以回答时，明确说“材料中未提及”，并指出还缺什么信息。"
    "公式与代码保持原样，不翻译。"
)


class LLMUnavailable(RuntimeError):
    pass


def chat(messages: list[dict], temperature: float = 0.2, max_tokens: int = 2048) -> str:
    if not llm_ready():
        raise LLMUnavailable("未配置大模型")
    headers = {"Content-Type": "application/json"}
    if LLM_API_KEY:
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    with httpx.Client(timeout=LLM_TIMEOUT) as client:
        r = client.post(f"{LLM_BASE_URL}/chat/completions", headers=headers, json=payload)
        if r.status_code >= 400:
            raise LLMUnavailable(f"模型接口返回 {r.status_code}: {r.text[:200]}")
        data = r.json()
    return (data["choices"][0]["message"]["content"] or "").strip()


def ask(question: str, context: str, history: list[dict] | None = None) -> str:
    msgs = [{"role": "system", "content": SYSTEM}]
    if history:
        msgs.extend(history[-6:])
    msgs.append({
        "role": "user",
        "content": f"材料如下：\n\n{context}\n\n问题：{question}\n\n请用中文回答，并在句末标注 [编号]。",
    })
    return chat(msgs)


def translate(text: str, target: str = "zh") -> str:
    prompt = (
        f"把下面的学术文本翻译成{'简体中文' if target == 'zh' else '英文'}。"
        "要求：术语准确、语句通顺；公式、代码、文献编号、专有名词缩写保持原样；只输出译文。\n\n"
        f"{text}"
    )
    return chat([{"role": "system", "content": "你是专业学术翻译。"},
                 {"role": "user", "content": prompt}], temperature=0.1, max_tokens=2048)


def summarize_findings(items: str) -> str:
    return chat([
        {"role": "system", "content": "你是科研综述作者。只依据给定材料，不虚构。"},
        {"role": "user", "content": f"材料：\n{items}\n\n请写一段 300 字以内的领域综述：脉络、代表工作、共识与分歧。引用处标注 [编号]。"},
    ], temperature=0.3)


def future_work(items: str, years: str) -> str:
    return chat([
        {"role": "system", "content": "你是资深审稿人。"},
        {"role": "user", "content": (
            f"材料（含发表年份）：\n{items}\n\n"
            "基于这些论文的 Future Work / Limitation 部分，提出 3-5 个下一步值得做的研究方向。"
            "要求：不要提已被最新论文做过的东西；每条注明它来自哪篇的哪句 [编号]。"
        )},
    ], temperature=0.4)


def outline(idea: str, refs: str) -> str:
    return chat([
        {"role": "system", "content": "你是论文写作教练。参考文献只能来自给定清单，不得虚构。"},
        {"role": "user", "content": (
            f"研究想法：{idea}\n\n可用参考文献（真实存在于文库）：\n{refs}\n\n"
            "请生成论文框架：Abstract / Introduction / Related Work / Method / Experiments / Conclusion 的要点提纲，"
            "并在 Related Work 处标注应引用哪几篇（用清单里的编号）。用 Markdown 输出。"
        )},
    ], temperature=0.4, max_tokens=3000)


SPECS = {
    "mermaid": ("Mermaid", "```mermaid"),
    "tikz": ("LaTeX TikZ", "```latex"),
    "graphviz": ("Graphviz DOT", "```dot"),
}


def diagram(desc: str, kind: str = "mermaid") -> str:
    """kind: mermaid | tikz | graphviz"""
    name, fence = SPECS.get((kind or "mermaid").lower(), SPECS["mermaid"])
    return chat([
        {"role": "system", "content": "你是擅长学术绘图的工程师。"},
        {"role": "user", "content": (
            f"用 {name} 语法画一张论文架构图：{desc}\n"
            f"只输出代码块（以 {fence} 开头），节点命名简洁，不要解释。"
        )},
    ], temperature=0.2, max_tokens=1600)


def search_terms(question: str) -> str:
    """把中文问题压成一行英文检索关键词（用于跨语言检索召回）。"""
    return chat([
        {"role": "system", "content": "你是检索式生成器。"},
        {"role": "user", "content": (
            f"问题：{question}\n\n输出一行英文检索关键词（3-8 个词，空格分隔），"
            "覆盖问题里的学术术语与同义词，不要解释，不要标点。"
        )},
    ], temperature=0.1, max_tokens=60).replace("\n", " ").strip()


def rerank(question: str, candidates: list[dict], keep: int = 8) -> list[int]:
    """让模型从候选片段里挑出与问题最相关的编号（跨语言语义匹配，弥补 BM25 词面不足）。"""
    lines = []
    for i, c in enumerate(candidates, 1):
        body = " ".join(c["text"].split())[:150]
        lines.append(f"{i}. p{c['page']} [{c['section'][:26]}] {body}")
    prompt = (
        f"问题：{question}\n\n候选片段：\n" + "\n".join(lines) +
        f"\n\n请选出最能回答该问题的片段编号（最多 {keep} 个），按相关度从高到低，"
        "只输出编号，用英文逗号分隔，不要解释。"
    )
    raw = chat([{"role": "system", "content": "你是检索重排器，只输出编号。"},
                {"role": "user", "content": prompt}], temperature=0.0, max_tokens=80)
    nums = [int(x) for x in re.findall(r"\d+", raw)]
    return [n for n in nums if 1 <= n <= len(candidates)][:keep]


def figure_caption(desc: str, stats: str) -> str:
    return chat([
        {"role": "system", "content": "你是论文图表说明撰写者。"},
        {"role": "user", "content": (
            f"图表内容：{desc}\n数据特征：{stats}\n\n"
            "写一条符合学术规范的 Figure caption（英文，一句话说清画了什么、横纵轴是什么、趋势结论是什么），再给一句中文说明。"
        )},
    ], temperature=0.2, max_tokens=400)
