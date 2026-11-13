"""入库管线：指纹去重 → 版本比对 → 解析 → 段落/参考文献落库。"""
from __future__ import annotations

import json
import re
import shutil
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .config import DEDUPE_THRESHOLD, PDF_DIR
from .db import exec_, one, q
from .parser import content_fingerprint, minhash_similarity, parse_pdf


def _index_path(pid: int) -> Path:
    from .config import DATA_DIR
    d = DATA_DIR / "index"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{pid}.json"


def save_struct(pid: int, struct: dict) -> None:
    _index_path(pid).write_text(json.dumps(struct, ensure_ascii=False), encoding="utf-8")


def load_struct(pid: int) -> dict | None:
    p = _index_path(pid)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _version_diff(a: dict, b: dict) -> dict:
    """a = 库里已有的，b = 新上传的。"""
    a_out = [o["title"] for o in a.get("outline", [])]
    b_out = [o["title"] for o in b.get("outline", [])]
    sm = SequenceMatcher(None, a_out, b_out)
    added = [b_out[j2] for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag in ("insert", "replace") for j2 in range(j1, j2)]
    removed = [a_out[i1] for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag in ("delete", "replace") for i1 in range(i1, i2)]
    return {
        "pages": [a["meta"]["n_pages"], b["meta"]["n_pages"]],
        "chars": [a["meta"]["n_chars"], b["meta"]["n_chars"]],
        "refs": [a["meta"]["n_refs"], b["meta"]["n_refs"]],
        "figures": [a["meta"]["n_figures"], b["meta"]["n_figures"]],
        "tables": [a["meta"]["n_tables"], b["meta"]["n_tables"]],
        "sections_added": added[:8],
        "sections_removed": removed[:8],
    }


def _newer_hint(existing: dict, incoming: dict) -> str:
    """粗判哪一版更新：页数/字符数/参考文献数更多，或文件名带更大版本号。"""
    ea, ia = existing["meta"], incoming["meta"]
    score_a = ea["n_pages"] * 2 + ea["n_chars"] // 2000 + ea["n_refs"]
    score_b = ia["n_pages"] * 2 + ia["n_chars"] // 2000 + ia["n_refs"]
    if score_b > score_a * 1.05:
        return "incoming"
    if score_a > score_b * 1.05:
        return "existing"
    return "same"


def _title_author_score(existing_meta: dict, incoming_meta: dict) -> dict:
    """标题/摘要/首作者综合判定：同一篇论文不同版本，排版会变，但标题与摘要稳定。"""
    a_t = re.sub(r"\W+", " ", (existing_meta.get("title") or "").lower()).strip()
    b_t = re.sub(r"\W+", " ", (incoming_meta.get("title") or "").lower()).strip()
    title_sim = SequenceMatcher(None, a_t, b_t).ratio() if a_t and b_t else 0.0
    if a_t and b_t and (a_t in b_t or b_t in a_t):
        title_sim = max(title_sim, 0.95)

    a_abs = re.sub(r"\s+", " ", (existing_meta.get("abstract") or "").lower())[:320]
    b_abs = re.sub(r"\s+", " ", (incoming_meta.get("abstract") or "").lower())[:320]
    abs_sim = SequenceMatcher(None, a_abs, b_abs).ratio() if a_abs and b_abs else 0.0

    a_auth = (existing_meta.get("authors") or "").split(",")[0].split("∗")[0].strip().lower()
    b_auth = (incoming_meta.get("authors") or "").split(",")[0].split("∗")[0].strip().lower()
    author_hit = bool(a_auth and b_auth and a_auth.split()[:2] == b_auth.split()[:2])
    return {"title": title_sim, "abstract": abs_sim, "author": author_hit}


def ingest(path: str | Path, display_name: str | None = None,
           on_duplicate: str = "ask") -> dict[str, Any]:
    """on_duplicate: ask(返回给前端选择) | keep_both | replace"""
    src = Path(path)
    name = display_name or src.name
    sha, sig = content_fingerprint(src)
    struct = parse_pdf(src)

    dupes: list[dict] = []
    for row in q("SELECT id, title, minhash, meta_json, filename FROM papers"):
        old_meta = json.loads(row["meta_json"] or "{}")
        mh = 0.0
        if row["minhash"]:
            mh = minhash_similarity(sig, json.loads(row["minhash"]))
        sigs = _title_author_score(old_meta, struct["meta"])
        # 同一篇论文的不同版本：标题高度一致且摘要相近
        same_paper = (sigs["title"] >= 0.85 and sigs["abstract"] >= 0.45) or \
                     (sigs["title"] >= 0.95 and sigs["author"])
        score = round(max(mh, 0.6 * sigs["title"] + 0.4 * sigs["abstract"]), 3)
        if same_paper or mh >= DEDUPE_THRESHOLD:
            old_struct = load_struct(row["id"]) or {"meta": old_meta, "outline": []}
            dupes.append({"id": row["id"], "title": row["title"], "filename": row["filename"],
                          "similarity": max(score, 0.9 if same_paper else score), "meta": old_struct["meta"],
                          "signals": sigs, "minhash": round(mh, 3)})

    if dupes and on_duplicate != "keep_both":
        old = max(dupes, key=lambda d: d["similarity"])
        old_struct = load_struct(old["id"]) or {"meta": old["meta"], "outline": []}
        hint = _newer_hint(old_struct, struct)
        diff = _version_diff(old_struct, struct)
        if on_duplicate == "ask":
            return {
                "status": "duplicate",
                "existing": {"id": old["id"], "title": old["title"], "filename": old["filename"], "meta": old["meta"]},
                "similarity": old["similarity"],
                "signals": old["signals"],
                "newer": hint,
                "suggestion": ("库里版本更新，建议保留库里版本" if hint == "existing"
                               else "新上传版本更新，建议用新版本覆盖" if hint == "incoming" else "两版内容相当，建议保留其一"),
                "diff": diff,
                "incoming_meta": struct["meta"],
                "staged": _stage(src, name),
            }
        if on_duplicate == "replace" and hint == "incoming":
            exec_("DELETE FROM chunks WHERE paper_id=?", (old["id"],))
            exec_("DELETE FROM refs WHERE paper_id=?", (old["id"],))
            exec_("DELETE FROM papers WHERE id=?", (old["id"],))
            exec_("DELETE FROM translations WHERE paper_id=?", (old["id"],))

    return _insert(struct, src, name, sha, sig)



def _stage(src: Path, name: str) -> str:
    """重复文件先放到 staging，用户确认后再入库。"""
    from .config import DATA_DIR
    st = DATA_DIR / "staging"
    st.mkdir(parents=True, exist_ok=True)
    dst = st / f"{abs(hash(name)) % (10**10)}_{name}"
    if src.resolve() != dst.resolve():
        shutil.copy2(src, dst)
    return str(dst)


def _insert(struct: dict, src: Path, name: str, sha: str, sig: list[int]) -> dict:
    dst = PDF_DIR / name
    if src.resolve() != dst.resolve():
        shutil.copy2(src, dst)
    meta = struct["meta"]
    pid = exec_(
        """INSERT INTO papers(filename,path,sha256,minhash,title,authors,year,n_pages,n_chars,size,status,meta_json)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (name, str(dst), sha, json.dumps(sig), meta["title"], meta["authors"], meta["year"],
         meta["n_pages"], meta["n_chars"], dst.stat().st_size, "ready", json.dumps(meta, ensure_ascii=False)),
    )
    for i, c in enumerate(struct["chunks"]):
        exec_("INSERT INTO chunks(paper_id,page,section,ordinal,text) VALUES(?,?,?,?,?)",
              (pid, c["page"], c["section"], i, c["text"]))
    for r in struct["refs"]:
        exec_("INSERT INTO refs(paper_id,raw,title,authors,year,arxiv_id) VALUES(?,?,?,?,?,?)",
              (pid, r["raw"], r["title"], r["authors"], r["year"], r["arxiv_id"]))
    save_struct(pid, struct)
    return {"status": "ingested", "id": pid, "meta": meta, "name": name}


def stage_ingest(staged_path: str, name: str) -> dict:
    sha, sig = content_fingerprint(staged_path)
    struct = parse_pdf(staged_path)
    return _insert(struct, Path(staged_path), name, sha, sig)


def delete_paper(pid: int) -> None:
    row = one("SELECT path FROM papers WHERE id=?", (pid,))
    exec_("DELETE FROM chunks WHERE paper_id=?", (pid,))
    exec_("DELETE FROM refs WHERE paper_id=?", (pid,))
    exec_("DELETE FROM translations WHERE paper_id=?", (pid,))
    exec_("DELETE FROM papers WHERE id=?", (pid,))
    idx = _index_path(pid)
    if idx.exists():
        idx.unlink()
    if row and Path(row["path"]).exists():
        Path(row["path"]).unlink()
