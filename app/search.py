"""检索层：BM25（英文词 + 中文二元组），带页码/章节标注，供 RAG 引用定位。"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from .config import TOP_K
from .db import q

_TOKEN = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    text = text.lower()
    toks: list[str] = []
    for m in _TOKEN.finditer(text):
        s = m.group(0)
        if "\u4e00" <= s[0] <= "\u9fff":
            toks.append(s)
        else:
            if len(s) > 1 or s.isdigit():
                toks.append(s)
    # 中文二元组，提高中文检索召回
    cjk = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    for run in cjk:
        for i in range(len(run) - 1):
            toks.append(run[i:i + 2])
    return toks


class Index:
    """内存倒排索引，论文数量变化时重建。"""

    def __init__(self) -> None:
        self.docs: list[dict[str, Any]] = []
        self.postings: dict[str, list[tuple[int, int]]] = {}
        self.doc_len: list[int] = []
        self.avg_len: float = 0.0
        self.n_docs: int = 0
        self.version: int = -1

    def rebuild(self) -> None:
        rows = q("""SELECT c.id, c.paper_id, c.page, c.section, c.text, p.title
                   FROM chunks c JOIN papers p ON p.id = c.paper_id""")
        self.docs = [dict(r) for r in rows]
        self.postings = {}
        self.doc_len = []
        for i, d in enumerate(self.docs):
            toks = tokenize(d["text"])
            self.doc_len.append(len(toks) or 1)
            for t, tf in Counter(toks).items():
                self.postings.setdefault(t, []).append((i, tf))
        self.n_docs = len(self.docs)
        self.avg_len = (sum(self.doc_len) / self.n_docs) if self.n_docs else 0.0

    def ensure(self) -> None:
        from .db import one
        cnt = (one("SELECT COUNT(*) AS n FROM chunks") or {"n": 0})["n"]
        if cnt != self.version:
            self.rebuild()
            self.version = cnt

    def search(self, query: str, k: int = TOP_K, paper_ids: list[int] | None = None) -> list[dict]:
        self.ensure()
        if not self.n_docs:
            return []
        qt = tokenize(query)
        if not qt:
            return []
        k1, b = 1.5, 0.75
        scores: dict[int, float] = {}
        for t in qt:
            plist = self.postings.get(t)
            if not plist:
                continue
            idf = math.log(1 + (self.n_docs - len(plist) + 0.5) / (len(plist) + 0.5))
            for i, tf in plist:
                if paper_ids and self.docs[i]["paper_id"] not in paper_ids:
                    continue
                dl = self.doc_len[i]
                s = idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / (self.avg_len or 1)))
                txt = self.docs[i]["text"]
                # 图表标题、页眉页脚、纯数字行降权：不是正文论据
                head = txt.lstrip()[:14].lower()
                if head.startswith(("figure", "table", "fig.", "tab.", "图 ", "表 ")) or \
                        sum(c.isdigit() for c in txt) / max(len(txt), 1) > 0.35:
                    s *= 0.55
                scores[i] = scores.get(i, 0.0) + s
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])[:k]
        out = []
        for i, s in ranked:
            d = dict(self.docs[i])
            d["score"] = round(s, 3)
            out.append(d)
        return out


INDEX = Index()


def build_context(hits: list[dict]) -> tuple[str, list[dict]]:
    """把检索结果拼成带编号的上下文，并返回引用清单。"""
    parts, cites = [], []
    for n, h in enumerate(hits, 1):
        parts.append(
            f"[{n}] 论文《{h['title']}》 第 {h['page']} 页 · {h['section']}\n{h['text']}"
        )
        cites.append({
            "n": n,
            "paper_id": h["paper_id"],
            "title": h["title"],
            "page": h["page"],
            "section": h["section"],
            "snippet": h["text"][:220],
        })
    return "\n\n".join(parts), cites
