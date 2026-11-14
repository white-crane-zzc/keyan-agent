"""FastAPI 服务：文库、阅读、问答、翻译、图谱、写作、推荐。"""
from __future__ import annotations

import io
import json
import re
import shutil
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from . import arxiv, graph as graphmod, llm, pipeline
from .config import DB_PATH, LLM_MODEL, PAGE_DIR, PLOT_DIR, STATIC_DIR, TOP_K, llm_ready
from .db import exec_, init_db, one, q
from .search import INDEX, build_context, expand_by_section, expand_query, hybrid_search, section_cover

app = FastAPI(title="科研小助手 Agent", version="1.0")


@app.on_event("startup")
def _startup() -> None:
    init_db()
    _start_refresh_job()


def _start_refresh_job() -> None:
    """定期刷新 arXiv 推荐（默认 6 小时一次，结果落库，前端推荐页直接读缓存）。"""
    import os
    import threading
    import time

    hours = float(os.getenv("RECOMMEND_REFRESH_HOURS", "6") or 6)
    if hours <= 0:
        return

    def loop():
        while True:
            try:
                arxiv.recommend(8)
            except Exception:
                pass
            time.sleep(hours * 3600)

    threading.Thread(target=loop, daemon=True, name="arxiv-refresh").start()


@app.get("/api/status")
def status() -> dict:
    counts = {
        "papers": (one("SELECT COUNT(*) n FROM papers") or {"n": 0})["n"],
        "chunks": (one("SELECT COUNT(*) n FROM chunks") or {"n": 0})["n"],
        "refs": (one("SELECT COUNT(*) n FROM refs") or {"n": 0})["n"],
    }
    return {"ok": True, "llm_ready": llm_ready(), "model": LLM_MODEL, **counts}


# ---------------- 文库 ----------------
@app.get("/api/papers")
def list_papers() -> dict:
    rows = [dict(r) for r in q(
        "SELECT id,filename,title,authors,year,n_pages,n_chars,size,added_at,meta_json FROM papers ORDER BY id DESC")]
    for r in rows:
        r["n_refs"] = (one("SELECT COUNT(*) n FROM refs WHERE paper_id=?", (r["id"],)) or {"n": 0})["n"]
        meta = json.loads(r.pop("meta_json") or "{}")
        r["n_figures"] = meta.get("n_figures", 0)
        r["n_tables"] = meta.get("n_tables", 0)
        r["columns"] = meta.get("columns", 1)
    return {"papers": rows}



@app.delete("/api/papers/{pid}")
def remove_paper(pid: int) -> dict:
    try:
        pipeline.delete_paper(pid)
    except PermissionError as e:
        raise HTTPException(500, f"文件正在被占用：{e}")
    INDEX.version = -1
    return {"ok": True}


@app.get("/api/papers/{pid}/struct")
def paper_struct(pid: int) -> dict:
    st = pipeline.load_struct(pid)
    if not st:
        raise HTTPException(404, "没有该论文的解析结果")
    row = one("SELECT * FROM papers WHERE id=?", (pid,))
    refs = q("SELECT raw, title, authors, year, arxiv_id FROM refs WHERE paper_id=? ORDER BY id", (pid,))
    return {"meta": json.loads(row["meta_json"] or "{}"), "outline": st["outline"],
            "abstract": st.get("meta", {}).get("abstract", ""),
            "counts": {k: st["meta"][k] for k in ("n_tables", "n_figures", "n_refs")},
            "refs": [dict(r) for r in refs],
            "tables": st["tables"][:6], "figures": st["figures"][:6]}


@app.get("/api/papers/{pid}/pdf")
def paper_pdf(pid: int):
    row = one("SELECT path FROM papers WHERE id=?", (pid,))
    if not row or not Path(row["path"]).exists():
        raise HTTPException(404, "PDF 不存在")
    return FileResponse(row["path"], media_type="application/pdf")


@app.get("/api/papers/{pid}/page/{n}")
def paper_page(pid: int, n: int, dpi: int = 150):
    """返回该页渲染图 + 文本块坐标（阅读器覆盖层用）。"""
    st = pipeline.load_struct(pid)
    row = one("SELECT path FROM papers WHERE id=?", (pid,))
    if not st or not row:
        raise HTTPException(404, "没有该论文")
    if n < 1 or n > len(st["pages"]):
        raise HTTPException(404, "页码超出范围")
    d = PAGE_DIR / str(pid)
    d.mkdir(parents=True, exist_ok=True)
    img = d / f"{n}@{dpi}.png"
    if not img.exists():
        import pymupdf as fitz
        doc = fitz.open(row["path"])
        page = doc[n - 1]
        pix = page.get_pixmap(dpi=dpi)
        pix.save(str(img))
        doc.close()
    page_info = st["pages"][n - 1]
    return {
        "n": n, "w": page_info["w"], "h": page_info["h"], "columns": page_info["columns"],
        "image": f"/api/papers/{pid}/page/{n}/png?dpi={dpi}",
        "blocks": [{"bbox": b["bbox"], "text": b["text"], "size": b["size"]} for b in page_info["blocks"]],
        "total_pages": len(st["pages"]),
    }


@app.get("/api/papers/{pid}/page/{n}/png")
def paper_page_png(pid: int, n: int, dpi: int = 150):
    d = PAGE_DIR / str(pid)
    img = d / f"{n}@{dpi}.png"
    if not img.exists():
        paper_page(pid, n, dpi)
    return FileResponse(img, media_type="image/png")


# ---------------- 上传与去重 ----------------
@app.post("/api/upload")
async def upload(files: list[UploadFile] = File(...), on_duplicate: str = Form("ask")) -> dict:
    results = []
    tmpdir = PAGE_DIR.parent / "upload_tmp"
    tmpdir.mkdir(parents=True, exist_ok=True)
    for f in files:
        if not f.filename.lower().endswith(".pdf"):
            results.append({"status": "error", "name": f.filename, "message": "只支持 PDF"})
            continue
        tmp = tmpdir / Path(f.filename).name
        with open(tmp, "wb") as out:
            shutil.copyfileobj(f.file, out)
        try:
            results.append(await run_in_threadpool(
                pipeline.ingest, tmp, Path(f.filename).name, on_duplicate))
        except Exception as e:
            results.append({"status": "error", "name": f.filename, "message": str(e)})
        finally:
            if tmp.exists():                       # 已入库或已转存 staging，临时副本可以删了
                tmp.unlink()
    INDEX.version = -1
    return {"results": results}


@app.post("/api/upload/confirm")
def upload_confirm(payload: dict = Body(...)) -> dict:
    staged = payload.get("staged")
    name = payload.get("name")
    action = payload.get("action", "cancel")          # cancel | keep_new | keep_both
    existing_id = payload.get("existing_id")
    if action == "cancel":
        if staged and Path(staged).exists():
            Path(staged).unlink()
        return {"status": "cancelled"}
    if not staged or not Path(staged).exists():
        raise HTTPException(404, "待确认文件已不存在")
    replace_id = int(existing_id) if (action == "keep_new" and existing_id) else None
    res = pipeline.stage_ingest(staged, name, replace_id)
    if Path(staged).exists():
        Path(staged).unlink()                          # 已入库，清掉暂存副本
    INDEX.version = -1
    return res


@app.post("/api/ingest/arxiv")
def ingest_arxiv(payload: dict = Body(...)) -> dict:
    ids = payload.get("ids") or []
    query = payload.get("query")
    maxn = int(payload.get("max", 5))
    results = []
    targets = []
    if ids:
        targets = [{"arxiv_id": i, "title": ""} for i in ids]
    elif query:
        targets = arxiv.search_arxiv(query, max_results=maxn)
    for t in targets:
        try:
            path = arxiv.download(t["arxiv_id"])
            r = pipeline.ingest(path, path.name)
            results.append({"status": r.get("status"), "id": r.get("id"), "arxiv_id": t["arxiv_id"],
                            "title": r.get("meta", {}).get("title") or t.get("title")})
        except Exception as e:
            results.append({"status": "error", "arxiv_id": t["arxiv_id"], "message": str(e)})
    INDEX.version = -1
    return {"results": results}


# ---------------- 问答 ----------------
@app.post("/api/ask")
def ask(payload: dict = Body(...)) -> dict:
    question = (payload.get("question") or "").strip()
    paper_ids = payload.get("paper_ids") or []
    top_k = int(payload.get("top_k") or TOP_K)
    if not question:
        raise HTTPException(400, "问题不能为空")
    extras = expand_query(question)
    if llm_ready() and any("\u4e00" <= ch <= "\u9fff" for ch in question):
        try:  # 有模型时用模型把中文问题压成英文检索式，跨语言召回更准
            terms = llm.search_terms(question)
            if terms:
                extras.insert(0, terms)
        except llm.LLMUnavailable:
            pass
    cover = list(paper_ids)
    if len(cover) < 2 and re.search(r"对比|区别|不同|相比|差异|比较", question):
        cover = [row["id"] for row in q("SELECT id FROM papers ORDER BY id")]
    hits = hybrid_search(question, k=top_k, paper_ids=paper_ids or None,
                         extra_queries=extras, cover_papers=cover if len(cover) > 1 else None)
    hits = expand_by_section(hits)
    if len(paper_ids) == 1:  # 单篇问题再补一章一块，覆盖全文各章节
        seen = {(h["paper_id"], h["page"], h["text"][:60]) for h in hits}
        for h in section_cover(paper_ids[0], question, extras):
            key = (h["paper_id"], h["page"], h["text"][:60])
            if key not in seen:
                hits.append(h)
                seen.add(key)
    if llm_ready() and len(hits) > top_k:
        # 候选多时让模型按语义重排（中文问英文表格全靠这一步）
        cand = hybrid_search(question, k=30, paper_ids=paper_ids or None, extra_queries=extras)
        seen = {(h["paper_id"], h["page"], h["text"][:60]) for h in hits}
        for h in cand:
            key = (h["paper_id"], h["page"], h["text"][:60])
            if key not in seen:
                hits.append(h)
                seen.add(key)
        pool = hits[:30]
        try:
            idxs = llm.rerank(question, pool, keep=top_k)
            if idxs:
                picked = [pool[i - 1] for i in idxs]
                rest = [h for h in pool if h not in picked]
                hits = picked + rest[:max(0, top_k - len(picked))]
        except llm.LLMUnavailable:
            hits = hits[:top_k]
    if not hits:
        return {"answer": "文库里没有检索到相关内容，请先上传论文。", "citations": [], "hits": []}
    context, cites = build_context(hits)
    if not llm_ready():
        return {
            "answer": (
                "（当前未配置大模型，下面是检索到的原文证据，可直接比对）\n\n"
                + "\n\n".join(f"[{c['n']}] 《{c['title']}》第 {c['page']} 页：{c['snippet']}" for c in cites)
            ),
            "citations": cites, "hits": hits, "degraded": True,
        }
    try:
        answer = llm.ask(question, context, payload.get("history"))
    except llm.LLMUnavailable as e:
        raise HTTPException(502, str(e))
    return {"answer": answer, "citations": cites, "hits": hits}


# ---------------- 翻译 ----------------
@app.post("/api/translate")
def translate(payload: dict = Body(...)) -> dict:
    text = (payload.get("text") or "").strip()
    target = payload.get("target", "zh")
    if not text:
        raise HTTPException(400, "文本为空")
    if len(text) > 4000:
        text = text[:4000]
    if not llm_ready():
        return {"text": text, "degraded": True, "notice": "未配置大模型，翻译不可用"}
    try:
        return {"text": llm.translate(text, target)}
    except llm.LLMUnavailable as e:
        raise HTTPException(502, str(e))


@app.post("/api/translate/range")
def translate_range(payload: dict = Body(...)) -> dict:
    pid = int(payload["paper_id"])
    p_from = int(payload.get("page_from") or 1)
    p_to = int(payload.get("page_to") or p_from)
    limit = int(payload.get("limit") or 60)
    rows = q("""SELECT id,page,section,text FROM chunks
                WHERE paper_id=? AND page BETWEEN ? AND ? ORDER BY ordinal LIMIT ?""",
             (pid, p_from, p_to, limit))
    if not llm_ready():
        return {"items": [{"chunk_id": r["id"], "page": r["page"], "section": r["section"],
                           "source": r["text"], "text": ""} for r in rows], "degraded": True}
    items = []
    for r in rows:
        cached = one("SELECT text FROM translations WHERE paper_id=? AND chunk_id=? AND lang='zh'", (pid, r["id"]))
        if cached:
            items.append({"chunk_id": r["id"], "page": r["page"], "section": r["section"],
                          "source": r["text"], "text": cached["text"], "cached": True})
            continue
        try:
            tr = llm.translate(r["text"])
        except llm.LLMUnavailable as e:
            raise HTTPException(502, str(e))
        exec_("INSERT OR REPLACE INTO translations(paper_id,chunk_id,lang,source,text) VALUES(?,?,?,?,?)",
              (pid, r["id"], "zh", r["text"], tr))
        items.append({"chunk_id": r["id"], "page": r["page"], "section": r["section"],
                      "source": r["text"], "text": tr})
    return {"items": items}


# ---------------- 图谱 / 综述 ----------------
@app.post("/api/graph")
def get_graph(payload: dict = Body(default={})) -> dict:
    return graphmod.build_graph(payload.get("paper_ids") or None)


@app.post("/api/survey")
def survey(payload: dict = Body(...)) -> dict:
    ids = payload.get("paper_ids") or []
    material = graphmod.citation_context(ids, limit=12)
    if not material:
        raise HTTPException(400, "没有可用材料")
    if not llm_ready():
        return {"text": material, "degraded": True}
    try:
        return {"text": llm.summarize_findings(material)}
    except llm.LLMUnavailable as e:
        raise HTTPException(502, str(e))


@app.post("/api/futurework")
def future_work(payload: dict = Body(...)) -> dict:
    ids = payload.get("paper_ids") or []
    if not ids:
        ids = [r["id"] for r in q("SELECT id FROM papers ORDER BY id DESC LIMIT 12")]
    material = graphmod.citation_context(ids, limit=12)
    if not material:
        raise HTTPException(400, "没有可用材料")
    if not llm_ready():
        return {"text": material, "degraded": True}
    years = ", ".join(str(r["year"]) for r in q("SELECT year FROM papers WHERE id IN (" + ",".join(map(str, ids)) + ")") if r["year"])
    try:
        return {"text": llm.future_work(material, years)}
    except llm.LLMUnavailable as e:
        raise HTTPException(502, str(e))


# ---------------- 写作助手 ----------------
@app.post("/api/write/outline")
def write_outline(payload: dict = Body(...)) -> dict:
    idea = (payload.get("idea") or "").strip()
    ids = payload.get("paper_ids") or []
    if not idea:
        raise HTTPException(400, "请先写研究想法")
    rows = q(f"SELECT id,title,year,authors FROM papers {'WHERE id IN (' + ','.join(map(str,ids)) + ')' if ids else ''} ORDER BY id")
    refs = "\n".join(f"[{i}] {r['title']} ({r['year']})" for i, r in enumerate(rows, 1))
    if not llm_ready():
        return {"text": "未配置大模型。可用参考文献清单：\n" + refs, "degraded": True}
    try:
        return {"text": llm.outline(idea, refs), "refs": [dict(r) for r in rows]}
    except llm.LLMUnavailable as e:
        raise HTTPException(502, str(e))


@app.post("/api/write/diagram")
def write_diagram(payload: dict = Body(...)) -> dict:
    desc = (payload.get("desc") or "").strip()
    kind = (payload.get("kind") or "mermaid").lower()
    if kind not in ("mermaid", "tikz", "graphviz"):
        kind = "mermaid"
    if not desc:
        raise HTTPException(400, "请描述架构")
    if not llm_ready():
        return {"text": "```mermaid\nflowchart LR\nA[输入] --> B[编码器] --> C[解码器] --> D[输出]\n```", "degraded": True}
    try:
        return {"text": llm.diagram(desc, kind)}
    except llm.LLMUnavailable as e:
        raise HTTPException(502, str(e))


@app.post("/api/plot")
async def plot(file: UploadFile = File(...), desc: str = Form(""), kind: str = Form("line")):
    raw = await file.read()
    try:
        if file.filename.lower().endswith(".csv"):
            df = pd.read_csv(io.BytesIO(raw))
        else:
            df = pd.read_excel(io.BytesIO(raw))
    except Exception as e:
        raise HTTPException(400, f"读取失败：{e}")
    if df.shape[1] < 2:
        raise HTTPException(400, "至少需要两列（x 与 y）")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 4.2), dpi=160)
    x = df.iloc[:, 0]
    ys = df.columns[1:]
    if kind == "bar":
        ax.bar(x.astype(str), df[ys[0]])
    elif kind == "radar":
        labels = list(df.iloc[:, 0].astype(str))
        vals = df[ys[0]].tolist()
        angles = [i / len(labels) * 2 * 3.14159 for i in range(len(labels))]
        angles += angles[:1]
        vals = vals + vals[:1]
        ax2 = plt.subplot(polar=True)
        ax2.plot(angles, vals)
        ax2.fill(angles, vals, alpha=0.2)
        ax2.set_xticks(angles[:-1])
        ax2.set_xticklabels(labels)
    else:
        for c in ys:
            ax.plot(x, df[c], marker="o", label=str(c))
        ax.legend()
    ax.grid(alpha=0.3)
    ax.set_xlabel(str(df.columns[0]))
    out = PLOT_DIR / f"plot_{abs(hash(file.filename + desc)) % 10**8}.png"
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    stats = f"行 {len(df)}，列 {list(df.columns)}，" + "；".join(
        f"{c} 均值{df[c].mean():.3g} 最大{df[c].max():.3g}" for c in ys if pd.api.types.is_numeric_dtype(df[c]))
    caption, caption_zh = "", ""
    if llm_ready():
        try:
            txt = llm.figure_caption(desc or file.filename, stats)
            caption, caption_zh = (txt.split("\n")[0], txt.split("\n")[-1]) if "\n" in txt else (txt, "")
        except Exception:
            pass
    return {"image": f"/api/plots/{out.name}", "caption": caption or f"{desc}", "caption_zh": caption_zh, "stats": stats}


@app.get("/api/plots/{name}")
def get_plot(name: str):
    p = PLOT_DIR / name
    if not p.exists():
        raise HTTPException(404, "图表不存在")
    return FileResponse(p, media_type="image/png")


# ---------------- 推荐 ----------------
@app.post("/api/recommend")
def recommend(payload: dict = Body(default={})) -> dict:
    limit = int(payload.get("limit") or 8)
    try:
        items = arxiv.recommend(limit)
    except Exception as e:
        raise HTTPException(502, f"抓取 arXiv 失败：{e}")
    return {"items": items}


@app.post("/api/feedback")
def feedback(payload: dict = Body(...)) -> dict:
    arxiv.feedback(payload["arxiv_id"], payload.get("verdict", "like"))
    return {"ok": True}


# ---------------- 重排导出（Markdown / HTML） ----------------
def _paper_markdown(pid: int) -> str:
    row = one("SELECT id, title, authors, year, filename FROM papers WHERE id=?", (pid,))
    if not row:
        raise HTTPException(404, "没有这篇论文")
    meta = json.loads(one("SELECT meta_json FROM papers WHERE id=?", (pid,))["meta_json"] or "{}")
    lines = [f"# {row['title'] or row['filename']}", ""]
    if row["authors"]:
        lines += [f"**作者**：{row['authors']}", ""]
    if row["year"]:
        lines += [f"**年份**：{row['year']}", ""]
    if meta.get("abstract"):
        lines += ["## 摘要", "", meta["abstract"], ""]
    chunks = q("SELECT page, section, text FROM chunks WHERE paper_id=? AND section != '参考文献' "
               "ORDER BY page, id", (pid,))
    cur = None
    for c in chunks:
        sec = c["section"] or "正文"
        if sec != cur:
            lines += ["", f"## {sec}", ""]
            cur = sec
        lines += [c["text"], ""]
    refs = q("SELECT raw, title, year FROM refs WHERE paper_id=? ORDER BY id", (pid,))
    if refs:
        lines += ["", "## 参考文献", ""]
        for i, r in enumerate(refs, 1):
            lines.append(f"[{i}] {r['raw'] or r['title']}")
    return "\n".join(lines)


@app.get("/api/papers/{pid}/export")
def export_paper(pid: int, fmt: str = "md"):
    md = _paper_markdown(pid)
    row = one("SELECT title, filename FROM papers WHERE id=?", (pid,))
    stem = re.sub(r"[^\w\u4e00-\u9fa5.-]+", "_", (row["title"] or row["filename"])[:60]) or f"paper_{pid}"
    if fmt == "html":
        import html as _html
        body = []
        for line in md.split("\n"):
            if line.startswith("## "):
                body.append(f"<h2>{_html.escape(line[3:])}</h2>")
            elif line.startswith("# "):
                body.append(f"<h1>{_html.escape(line[2:])}</h1>")
            elif line.strip():
                body.append(f"<p>{_html.escape(line)}</p>")
        page = ("<!doctype html><html lang='zh'><meta charset='utf-8'>"
                f"<title>{_html.escape(row['title'] or '')}</title>"
                "<style>body{max-width:820px;margin:40px auto;font:16px/1.75 system-ui,"
                "'Segoe UI',sans-serif;color:#222}h1{font-size:26px}h2{font-size:19px;"
                "margin-top:28px;border-bottom:1px solid #eee;padding-bottom:6px}</style>"
                f"<body>{''.join(body)}</body></html>")
        return Response(page, media_type="text/html; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{stem}.html"'})
    return Response(md, media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{stem}.md"'})


# ---------------- 按参考文献批量下载 + 引用价值筛选 ----------------
@app.post("/api/refs/batch")
def refs_batch(payload: dict = Body(...)) -> dict:
    pid = int(payload.get("paper_id") or 0)
    limit = int(payload.get("limit") or 20)
    do_download = bool(payload.get("download"))
    rows = q("SELECT id, raw, title, year, arxiv_id FROM refs WHERE paper_id=? ORDER BY id", (pid,))
    if not rows:
        raise HTTPException(404, "该论文没有解析出参考文献")
    # 正文里 [n] 被引次数：只出现一次的多半是"为引用而引用"（凑数引用）
    body = "\n".join(c["text"] for c in q(
        "SELECT text FROM chunks WHERE paper_id=? AND section != '参考文献'", (pid,)))
    counts = {}
    for m in re.finditer(r"\[(\d{1,3})\]", body):
        n = int(m.group(1))
        counts[n] = counts.get(n, 0) + 1
    items = []
    for i, r in enumerate(rows, 1):
        cnt = counts.get(i, 0)
        verdict, reason = "保留", ""
        if cnt == 0:
            verdict, reason = "存疑", "正文没有引用编号，可能是解析误并入或未被引用"
        elif cnt == 1:
            verdict, reason = "存疑", "全文仅引用 1 次，疑似凑数引用"
        items.append({"n": i, "title": r["title"] or (r["raw"] or "")[:90], "year": r["year"],
                      "arxiv_id": r["arxiv_id"], "cited": cnt, "verdict": verdict, "reason": reason})
    picked = [it for it in items if it["verdict"] == "保留" and it["arxiv_id"]][:limit]
    downloaded, failed = [], []
    if do_download:
        for it in picked:
            aid = it["arxiv_id"]
            try:
                arxiv.download(aid)
                downloaded.append(aid)
            except Exception as e:
                failed.append(f"{aid}: {e}")
    return {"total": len(items), "cited_only_once": sum(1 for it in items if it["cited"] == 1),
            "not_cited": sum(1 for it in items if it["cited"] == 0),
            "items": items[:60], "download_candidates": [it["arxiv_id"] for it in picked],
            "downloaded": downloaded, "failed": failed}


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
