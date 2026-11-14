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
                # 图表标题、页眉页脚、纯数字行降权：不是正文论据；表格块保留（参数表本身就是答案）
                if "表格" not in self.docs[i]["section"]:
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


# 中文学术术语 → 英文检索词：中文问题也能对上英文论文（无模型时的兜底）
TERM_MAP = {
    "多头注意力": ["multi-head attention", "multi head"],
    "自注意力": ["self-attention", "self attention"],
    "注意力": ["attention"],
    "位置编码": ["positional encoding", "position embedding"],
    "残差": ["residual"],
    "层归一化": ["layer normalization", "layernorm"],
    "前馈": ["feed-forward", "feed forward"],
    "编码器": ["encoder"],
    "解码器": ["decoder"],
    "预训练": ["pre-training", "pretrained"],
    "训练方式": ["training", "training objective", "optimizer", "Adam"],
    "训练": ["training", "train"],
    "微调": ["fine-tuning", "finetune"],
    "掩码": ["mask", "masked"],
    "双向": ["bidirectional"],
    "维度": ["dimension", "d_model"],
    "头数": ["heads"],
    "复杂度": ["complexity"],
    "超参数": ["hyperparameters", "hyperparameter", "layers hidden heads"],
    "预训练任务": ["masked language model", "next sentence prediction", "pre-training tasks"],
    "附录": ["appendix"],
    "超参数": ["hyperparameter"],
    "数据集": ["dataset", "corpus"],
    "准确率": ["accuracy"],
    "泛化": ["generalization"],
    "推理": ["inference"],
    "梯度": ["gradient"],
    "优化器": ["optimizer", "Adam"],
    "过拟合": ["overfitting"],
    "稀疏": ["sparse", "sparsity"],
    "损失": ["loss"],
    "实验": ["experiment"],
    "结论": ["conclusion"],
    "未来工作": ["future work"],
    "局限性": ["limitation"],
}


def expand_query(q: str) -> list[str]:
    """中文术语命中时，生成一条英文检索式。"""
    terms = [t for zh, ens in TERM_MAP.items() if zh in q for t in ens]
    return [" ".join(dict.fromkeys(terms))] if terms else []


def hybrid_search(query: str, k: int = TOP_K, paper_ids: list[int] | None = None,
                  extra_queries: list[str] | None = None,
                  cover_papers: list[int] | None = None) -> list[dict]:
    """原问题 + 英文检索式（词表或模型给出）多路检索，按 chunk 取最高分合并。

    cover_papers 非空时做配额召回：保证每篇论文至少进一条，否则多篇对比会全被一篇占满。
    """
    queries = [query] + (extra_queries if extra_queries is not None else expand_query(query))
    merged: dict[tuple, dict] = {}
    for qq in queries[:3]:
        for h in INDEX.search(qq, k=k * 2, paper_ids=paper_ids):
            key = (h["paper_id"], h["page"], h["text"][:60])
            if key not in merged or h["score"] > merged[key]["score"]:
                merged[key] = h
    ranked = sorted(merged.values(), key=lambda h: -h["score"])
    out = ranked[:k]
    if cover_papers:
        for pid in cover_papers:
            if any(h["paper_id"] == pid for h in out):
                continue
            cand = next((h for h in ranked if h["paper_id"] == pid), None)
            if not cand:
                # 该篇一条都没召回：用全部检索式（含英文）在篇内单独捞，取最高分
                best = None
                for qq in queries[:3]:
                    got = INDEX.search(qq, k=1, paper_ids=[pid])
                    if got and (best is None or got[0]["score"] > best["score"]):
                        best = got[0]
                cand = best
            if not cand:
                continue
            # 挤掉当前占比最大的那篇的末位条目，保持总数不变
            dom = max({h["paper_id"] for h in out},
                      key=lambda p: sum(1 for h in out if h["paper_id"] == p))
            idx = max(i for i, h in enumerate(out) if h["paper_id"] == dom)
            out[idx] = cand
    return out



def section_cover(paper_id: int, query: str, extra_queries: list[str] | None = None,
                  max_chunks: int = 10, per_section: int = 2) -> list[dict]:
    """单篇问"整篇/设置/结构"类问题时，补每个章节最相关的几块，避免答案卡在别的章节。"""
    seen_sec: dict[str, int] = {}
    out: list[dict] = []
    for qq in [query] + (extra_queries or [])[:2]:
        for h in INDEX.search(qq, k=150, paper_ids=[paper_id]):
            sec = h["section"]
            if seen_sec.get(sec, 0) >= per_section:
                continue
            seen_sec[sec] = seen_sec.get(sec, 0) + 1
            d = dict(h)
            d["score"] = round(h["score"] * 0.5, 3)
            out.append(d)
            if len(out) >= max_chunks:
                return out
    return out


def expand_by_section(hits: list[dict], max_extra: int = 4) -> list[dict]:
    """命中片段周边补上下文：同一章节里紧邻的块（超参数常和正文分块），避免"差一块就有答案"。"""
    seen = {(h["paper_id"], h["page"], h["text"][:60]) for h in hits}
    extra: list[dict] = []
    for h in hits[:3]:
        rows = q("""SELECT c.id, c.paper_id, c.page, c.section, c.text, p.title
                    FROM chunks c JOIN papers p ON p.id=c.paper_id
                    WHERE c.paper_id=? AND c.section=? AND c.page BETWEEN ? AND ?
                    ORDER BY c.ordinal LIMIT 6""",
                 (h["paper_id"], h["section"], h["page"] - 1, h["page"] + 1))
        for r in rows:
            key = (r["paper_id"], r["page"], r["text"][:60])
            if key in seen:
                continue
            d = dict(r)
            d["score"] = round(h["score"] * 0.6, 3)
            extra.append(d)
            seen.add(key)
            if len(extra) >= max_extra:
                return hits + extra
    return hits + extra


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
