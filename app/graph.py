"""引用网络：文库内引用关系、核心节点（基石/边缘论文）、综述素材聚合。"""
from __future__ import annotations

import re
from typing import Any

import networkx as nx

from .db import q


def _norm_title(t: str) -> str:
    t = re.sub(r"[^a-z0-9\u4e00-\u9fff ]", "", (t or "").lower())
    return re.sub(r"\s+", " ", t).strip()


def _title_match(a: str, b: str) -> bool:
    na, nb = _norm_title(a), _norm_title(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    wa, wb = set(na.split()), set(nb.split())
    if not wa or not wb:
        return False
    jac = len(wa & wb) / len(wa | wb)
    return jac >= 0.7 or (len(wa & wb) >= 4 and jac >= 0.5)


def _pagerank(G: nx.DiGraph, alpha: float = 0.85, iters: int = 60) -> dict[int, float]:
    """自实现 PageRank，避免额外依赖 scipy。"""
    import numpy as np
    nodes = list(G.nodes)
    if not nodes:
        return {}
    idx = {n: i for i, n in enumerate(nodes)}
    n = len(nodes)
    M = np.full((n, n), 1.0 / n)
    for u in nodes:
        outs = list(G.successors(u))
        if outs:
            for v in outs:
                M[idx[v], idx[u]] = 1.0 / len(outs)
        else:  # 悬挂节点均分
            M[:, idx[u]] = 1.0 / n
    v = np.full(n, 1.0 / n)
    for _ in range(iters):
        v = alpha * M.dot(v) + (1 - alpha) / n
    return {node: float(v[idx[node]]) for node in nodes}


def build_graph(paper_ids: list[int] | None = None) -> dict[str, Any]:
    papers = [dict(r) for r in q("SELECT id,title,year,n_pages,authors FROM papers")]
    note = ""
    if paper_ids:
        if len(paper_ids) >= 2:
            papers = [p for p in papers if p["id"] in paper_ids]
        else:
            # 只勾 1 篇时，图谱只有一个点、没有边，等于没画面。
            # 先补它的 1 跳邻居（它引用的 / 引用它的），邻居还是凑不出就退回全库。
            all_papers = papers
            seed = next((p for p in all_papers if p["id"] == paper_ids[0]), None)
            if seed:
                refs = [dict(r) for r in q("SELECT paper_id,title,raw FROM refs")]
                neigh = set()
                for r in refs:
                    if r["paper_id"] == seed["id"]:
                        for p in all_papers:
                            if p["id"] != seed["id"] and _title_match(r["title"] or r["raw"], p["title"]):
                                neigh.add(p["id"])
                    elif _title_match(r["title"] or r["raw"], seed["title"]):
                        neigh.add(r["paper_id"])
                neigh.discard(seed["id"])
                if neigh:
                    papers = [seed] + [p for p in all_papers if p["id"] in neigh]
                    note = f"只勾选了 1 篇，已自动补上它的直接引用邻居（共 {len(papers)} 篇）"
                else:
                    papers = all_papers
                    note = "只勾选了 1 篇且库内没有它的直接引用邻居，已改为全库图谱"
    ids = {p["id"] for p in papers}
    refs = [dict(r) for r in q("SELECT paper_id,title,raw,arxiv_id,year FROM refs")]

    G = nx.DiGraph()
    for p in papers:
        G.add_node(p["id"], title=p["title"], year=p["year"], **{k: p[k] for k in ("n_pages",)})

    edges = []
    external: dict[str, int] = {}
    for r in refs:
        if r["paper_id"] not in ids:
            continue
        target = None
        for p in papers:
            if p["id"] == r["paper_id"]:
                continue
            if _title_match(r["title"] or r["raw"], p["title"]):
                target = p["id"]
                break
        if target:
            if G.has_edge(r["paper_id"], target):
                G[r["paper_id"]][target]["w"] += 1
            else:
                G.add_edge(r["paper_id"], target, w=1)
            edges.append({"source": r["paper_id"], "target": target})
        else:
            key = (r["title"] or r["raw"])[:80]
            external[key] = external.get(key, 0) + 1

    metrics = {}
    if G.number_of_nodes():
        pr = _pagerank(G) if G.number_of_edges() else {n: 0.0 for n in G.nodes}
        for n in G.nodes:
            metrics[n] = {
                "in": G.in_degree(n),
                "out": G.out_degree(n),
                "pagerank": round(pr.get(n, 0.0), 4),
            }

    nodes = []
    max_in = max([metrics.get(p["id"], {}).get("in", 0) for p in papers], default=0)
    for p in papers:
        m = metrics.get(p["id"], {"in": 0, "out": 0, "pagerank": 0})
        role = "中间"
        if m["in"] > 0 and m["in"] >= max(1, max_in):
            role = "基石"
        elif m["in"] == 0 and m["out"] > 0:
            role = "边缘"
        nodes.append({"id": p["id"], "title": p["title"], "year": p["year"],
                      "in": m["in"], "out": m["out"], "pagerank": m["pagerank"], "role": role})

    core = [n for n in nodes if n["role"] == "基石"]
    peripheral = [n for n in nodes if n["in"] == 0 and n["out"] > 0]
    return {
        "nodes": nodes,
        "edges": edges,
        "core": [c["id"] for c in core],
        "peripheral": [c["id"] for c in peripheral],
        "external_top": sorted(external.items(), key=lambda kv: -kv[1])[:10],
        "stats": {"papers": len(nodes), "internal_edges": len(edges)},
        "note": note,
    }


def citation_context(paper_ids: list[int], limit: int = 10) -> str:
    """给综述/未来工作用的材料：每篇的摘要 + 未来工作段落。"""
    out = []
    cond = f"AND paper_id IN ({','.join(str(i) for i in paper_ids)})" if paper_ids else ""
    rows = q(f"""SELECT c.paper_id, c.page, c.section, c.text, p.title, p.year
                 FROM chunks c JOIN papers p ON p.id=c.paper_id
                 WHERE (LOWER(c.section) LIKE '%future%' OR LOWER(c.section) LIKE '%conclusion%'
                        OR LOWER(c.section) LIKE '%limitation%' OR LOWER(c.section) LIKE '%discussion%')
                 {cond} LIMIT 400""")
    n = 1
    for r in rows[:limit]:
        out.append(f"[{n}] 《{r['title']}》({r['year']}) {r['section']} 第{r['page']}页：{r['text'][:400]}")
        n += 1
    if len(out) < limit:
        for p in q(f"SELECT id,title,year,meta_json FROM papers {'WHERE id IN (' + ','.join(str(i) for i in paper_ids) + ')' if paper_ids else ''}"):
            import json
            meta = json.loads(p["meta_json"] or "{}")
            if meta.get("abstract"):
                out.append(f"[{n}] 《{p['title']}》({p['year']}) 摘要：{meta['abstract'][:400]}")
                n += 1
            if len(out) >= limit:
                break
    return "\n\n".join(out)
