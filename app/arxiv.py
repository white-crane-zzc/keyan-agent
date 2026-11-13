"""arXiv 集成：按编号/标题下载、抓取新论文、给出推荐理由。"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

from .config import ARXIV_API, ARXIV_PDF, PDF_DIR
from .db import exec_, q
from .search import INDEX, tokenize

NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def _sanitize(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:120]


def download(arxiv_id: str) -> Path:
    """arxiv_id 形如 1706.03762 或 1706.03762v7。"""
    aid = arxiv_id.strip()
    url = f"{ARXIV_PDF}{aid}"
    out = PDF_DIR / _sanitize(f"arXiv_{aid}.pdf")
    with httpx.Client(timeout=90, follow_redirects=True) as c:
        r = c.get(url, headers={"User-Agent": "research-assistant/1.0"})
        if r.status_code >= 400:
            raise RuntimeError(f"arXiv 下载失败 {r.status_code}: {aid}")
        out.write_bytes(r.content)
    return out


def search_arxiv(query: str, max_results: int = 8, sort: str = "relevance") -> list[dict]:
    params = {
        "search_query": query if ":" in query else f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance" if sort == "relevance" else "submittedDate",
        "sortOrder": "descending",
    }
    with httpx.Client(timeout=60) as c:
        r = c.get(ARXIV_API, params=params, headers={"User-Agent": "research-assistant/1.0"})
        r.raise_for_status()
        root = ET.fromstring(r.text)
    out = []
    for e in root.findall("a:entry", NS):
        aid_full = (e.findtext("a:id", default="", namespaces=NS) or "").rsplit("/", 1)[-1]
        title = (e.findtext("a:title", default="", namespaces=NS) or "").strip().replace("\n", " ")
        summ = re.sub(r"\s+", " ", e.findtext("a:summary", default="", namespaces=NS) or "")
        pub = (e.findtext("a:published", default="", namespaces=NS) or "")[:10]
        out.append({
            "arxiv_id": aid_full,
            "title": title,
            "summary": summ,
            "published": pub,
            "pdf_url": f"{ARXIV_PDF}{aid_full}",
            "has_code": bool(re.search(r"github\.com|code (is )?(available|released)", summ, re.I)),
        })
    return out


def recommend(limit: int = 10) -> list[dict]:
    """以文库已有论文的主题为种子，抓最近的 arXiv 新论文，按相关系数排序。"""
    rows = q("SELECT title, meta_json FROM papers ORDER BY id DESC LIMIT 12")
    if not rows:
        return []
    seeds = []
    import json
    for r in rows:
        meta = json.loads(r["meta_json"] or "{}")
        seeds.append((r["title"] or "") + " " + (meta.get("abstract") or "")[:300])
    seed_tokens = set()
    for s in seeds:
        seed_tokens |= set(tokenize(s))

    cats = "cat:cs.CL OR cat:cs.LG OR cat:cs.CV"
    cands = search_arxiv(cats, max_results=40, sort="recent")
    known = {r["title"] for r in rows}
    scored = []
    for c in cands:
        if c["title"] in known:
            continue
        toks = set(tokenize(c["title"] + " " + c["summary"]))
        overlap = len(toks & seed_tokens) / max(len(seed_tokens), 1)
        score = overlap * 100 + (15 if c["has_code"] else 0)
        reason_bits = []
        if overlap > 0.05:
            common = sorted(t for t in (toks & seed_tokens) if len(t) > 3)[:6]
            reason_bits.append("与你文库共享主题词：" + "、".join(common))
        if c["has_code"]:
            reason_bits.append("摘要中提到开源代码，便于复现")
        scored.append({**c, "score": round(score, 2), "reason": "；".join(reason_bits) or "近期同领域新工作"})
    scored.sort(key=lambda x: -x["score"])
    for s in scored[:limit]:
        exec_("""INSERT OR IGNORE INTO recs(arxiv_id,title,summary,pdf_url,score,reason,has_code)
                 VALUES(?,?,?,?,?,?,?)""",
              (s["arxiv_id"], s["title"], s["summary"][:2000], s["pdf_url"], s["score"], s["reason"], 1 if s["has_code"] else 0))
    return scored[:limit]


def feedback(arxiv_id: str, verdict: str) -> None:
    exec_("UPDATE recs SET feedback=? WHERE arxiv_id=?", (verdict, arxiv_id))
