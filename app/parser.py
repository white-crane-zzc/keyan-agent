"""PDF 细粒度解析：版面（单/双栏）、标题层级、摘要、表格、图表、公式、参考文献。"""
from __future__ import annotations

import hashlib
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

try:  # PyMuPDF 2.x 推荐新名字
    import pymupdf as fitz
except ImportError:  # 兼容旧版
    import fitz  # type: ignore

from .config import CHUNK_MAX_CHARS

MATH_CHARS = set("∑∫∏√≈≤≥±∓∂∇∞∈∉⊂⊃∪∩∝αβγδεζηθλμνξπρστφχψωΓΔΘΛΞΠΣΦΨΩ")
KEY_SECTIONS = {
    "abstract": 1, "摘要": 1, "introduction": 1, "引言": 1, "background": 1,
    "related work": 1, "related works": 1, "相关工作": 1,
    "method": 1, "methods": 1, "approach": 1, "方法": 1,
    "experiment": 1, "experiments": 1, "experimental setup": 1, "实验": 1,
    "result": 1, "results": 1, "结果": 1, "discussion": 1, "讨论": 1,
    "conclusion": 1, "conclusions": 1, "结论": 1, "limitations": 1,
    "future work": 1, "acknowledgements": 1, "acknowledgments": 1,
    "appendix": 1, "附录": 1, "references": 1, "bibliography": 1, "参考文献": 1,
}
NUM_PREFIX = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,3})\.?\s+(\S.*)$")
NUM_ONLY = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,3})\.?$")
ARXIV_STAMP = re.compile(r"^arxiv:\s*\d{4}\.\d{4,5}(v\d+)?\s*\[", re.I)
FIG_CAP = re.compile(r"^(figure|fig\.|table|图|表)\s*[0-9一二三四五六七八九十]+[.:：]?", re.I)
REF_ITEM = re.compile(r"^\[?(\d{1,3})\]?\s*(?:[\.\)、]\s*)?")
GITHUB = re.compile(r"github\.com/[A-Za-z0-9_.-]+", re.I)


def _norm(text: str) -> str:
    text = text.replace("\u00ad", "").replace("\u2010", "-")
    text = text.replace("\ufb01", "fi").replace("\ufb02", "fl").replace("\ufb00", "ff")
    text = re.sub(r"-\s*\n\s*", "", text)          # 断词连字符
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def _block_text(block: dict) -> str:
    out = []
    for line in block.get("lines", []):
        out.append("".join(s.get("text", "") for s in line.get("spans", [])))
    return _norm("\n".join(out))


def _block_font(block: dict) -> tuple[float, bool]:
    sizes, bold = [], False
    for line in block.get("lines", []):
        for s in line.get("spans", []):
            if s.get("text", "").strip():
                sizes.append(round(float(s.get("size", 0)), 1))
                if int(s.get("flags", 0)) & 16:
                    bold = True
    if not sizes:
        return 0.0, bold
    return Counter(sizes).most_common(1)[0][0], bold


def _is_math(text: str) -> bool:
    if not text or len(text) > 260:
        return False
    letters = [c for c in text if not c.isspace()]
    if not letters:
        return False
    mathish = sum(1 for c in letters if c in MATH_CHARS) / len(letters)
    eq_density = text.count("=") / max(len(text), 1)
    return mathish > 0.18 or (eq_density > 0.08 and mathish > 0.05)


def _detect_columns(blocks: list[dict], width: float) -> int:
    left = right = mid = 0
    for b in blocks:
        cx = (b["bbox"][0] + b["bbox"][2]) / 2
        w = b["bbox"][2] - b["bbox"][0]
        if w > width * 0.6:
            mid += 1
        elif cx < width * 0.5:
            left += 1
        else:
            right += 1
    total = max(left + right + mid, 1)
    if mid / total > 0.45:
        return 1
    if min(left, right) >= 3 and min(left, right) / total >= 0.22:
        return 2
    return 1


def _read_order(blocks: list[dict], ncol: int, width: float) -> list[dict]:
    if ncol == 1:
        return sorted(blocks, key=lambda b: (round(b["bbox"][1], 1), b["bbox"][0]))
    def key(b):
        w = b["bbox"][2] - b["bbox"][0]
        col = 0 if w > width * 0.6 else (0 if (b["bbox"][0] + b["bbox"][2]) / 2 < width * 0.5 else 1)
        return (col, round(b["bbox"][1], 1), b["bbox"][0])
    return sorted(blocks, key=key)


def _split_sentences(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    parts = re.split(r"(?<=[。！？.!?])\s+", text)
    out, buf = [], ""
    for p in parts:
        if len(buf) + len(p) + 1 > limit and buf:
            out.append(buf.strip())
            buf = p
        else:
            buf = (buf + " " + p).strip()
    if buf:
        out.append(buf.strip())
    return [p for p in out if p]


# ---------------- 结构识别 ----------------
def _merge_number_headings(blocks: list[dict]) -> list[dict]:
    """把「1」和「Introduction」这种被拆成两块的编号标题合回来。"""
    out: list[dict] = []
    i = 0
    while i < len(blocks):
        b = blocks[i]
        m = NUM_ONLY.match(b["text"].strip())
        if m and i + 1 < len(blocks) and blocks[i + 1]["page"] == b["page"]:
            nxt = blocks[i + 1]
            if 0 < len(nxt["text"]) < 80 and nxt["size"] >= b["size"] * 0.9:
                merged = dict(nxt)
                merged["text"] = f"{m.group(1)} {nxt['text'].strip()}"
                merged["bbox"] = [min(b["bbox"][0], nxt["bbox"][0]), min(b["bbox"][1], nxt["bbox"][1]),
                                  max(b["bbox"][2], nxt["bbox"][2]), max(b["bbox"][3], nxt["bbox"][3])]
                out.append(merged)
                i += 2
                continue
        out.append(b)
        i += 1
    return out


def heading_level(text: str, size: float, body: float, bold: bool) -> int:
    """返回 1/2/3 表示标题层级，0 表示正文。"""
    t = text.strip().replace("\n", " ")
    if not t or len(t) > 110:
        return 0
    if FIG_CAP.match(t) and len(t) > 20:
        return 0
    low = t.lower().strip(" :.")
    if low in KEY_SECTIONS:
        return 1
    # 表格行/数据行：数字占比过高，不是标题
    digits = sum(1 for c in t if c.isdigit())
    if digits / max(len(t), 1) > 0.30:
        return 0
    if len([w for w in t.split() if w.replace(".", "").isdigit()]) >= 5:
        return 0
    m = NUM_PREFIX.match(t)
    if m and size >= body * 0.97 and len(m.group(2)) < 100:
        depth = len(m.group(1).split("."))
        return 1 if depth == 1 else (2 if depth == 2 else 3)
    # 无编号：靠字号/加粗，且不能像正文句子
    ratio = size / body if body else 1
    looks_sentence = t.endswith((".", "。", "，", ",")) and len(t.split()) > 6
    if looks_sentence:
        return 0
    if ratio >= 1.55:
        return 1
    if ratio >= 1.22:
        return 2
    if bold and ratio >= 1.08 and len(t.split()) <= 8:
        return 3
    return 0


def _clean_title_candidates(page1: list[dict], body: float, page_h: float) -> list[dict]:
    cands = []
    for b in page1:
        t = b["text"].strip().replace("\n", " ")
        if ARXIV_STAMP.match(t) or re.match(r"^(proceedings|conference|published as|preprint)", t, re.I):
            continue
        if b["bbox"][1] > page_h * 0.55:
            continue
        if len(t) < 6 or len(t) > 220:
            continue
        if "@" in t or re.search(r"https?://", t):
            continue
        cands.append(b)
    return cands


def _guess_title(page1: list[dict], body: float, page_h: float, meta_title: str) -> str:
    cands = _clean_title_candidates(page1, body, page_h)
    if not cands:
        return meta_title or ""
    top = max(c["size"] for c in cands)
    same = [c for c in cands if abs(c["size"] - top) < 0.7]
    same.sort(key=lambda c: c["bbox"][1])
    joined = " ".join(c["text"].replace("\n", " ").strip() for c in same[:3]).strip()
    if len(joined) < 6 and meta_title:
        return meta_title
    return joined


def _guess_authors(page1: list[dict], title: str, body: float) -> str:
    t_y = None
    for b in page1:
        if title and b["text"].replace("\n", " ").strip() and b["text"].replace("\n", " ").strip() in title:
            t_y = b["bbox"][3]
            break
    if t_y is None:
        return ""
    picked = []
    for b in page1:
        t = b["text"].replace("\n", " ").strip()
        if b["bbox"][1] <= t_y or t.lower().startswith(("abstract", "摘要")):
            continue
        if "@" in t:
            break
        if 2 < len(t) < 400 and ("," in t or " and " in t or "∗" in t or "*" in t):
            picked.append(t)
        if len(picked) >= 2:
            break
    return re.sub(r"\s{2,}", " ", " ".join(picked)).strip()


def _find_refs_section(blocks: list[dict]) -> tuple[int, int]:
    """返回 (参考文献起始块下标, 结束下标)。找不到就用后 40% 页里密集出现 [n] 的区域兜底。"""
    for i, b in enumerate(blocks):
        low = b["text"].strip().lower().strip(" :.")
        if low in ("references", "bibliography", "参考文献") or low.startswith("references"):
            return i, len(blocks)
    start = None
    for i in range(int(len(blocks) * 0.5), len(blocks)):
        if REF_ITEM.match(blocks[i]["text"].strip()) and len(blocks[i]["text"]) > 40:
            start = i
            break
    return (-1, -1) if start is None else (start, len(blocks))


def _parse_refs(lines: list[str]) -> list[dict]:
    """优先按 [n] 编号切分；没有编号时退化为「作者块 + 年份块」合并。"""
    blocks = [l.strip() for l in lines if l.strip()]
    # 去掉混进来的标题行
    blocks = [b for b in blocks if b.lower().strip(" :.") not in ("references", "bibliography", "参考文献")]
    items, cur = [], ""
    for l in blocks:
        if re.match(r"^\[?\d{1,3}\]", l):
            if cur:
                items.append(cur)
            cur = l
        elif cur:
            cur = cur + " " + l if len(l) < 260 else cur
            if len(l) >= 260:
                items.append(cur)
                cur = ""
    if cur:
        items.append(cur)

    if len(items) < 3:  # 作者-年份格式（如 ACL/NAACL 排版）
        items, pending = [], ""
        for l in blocks:
            if re.search(r"(19|20)\d{2}", l):
                if pending:
                    l = pending + " " + l
                    pending = ""
                items.append(l)
            else:
                pending = (pending + " " + l).strip() if pending else l
        if pending and items:
            items[-1] += " " + pending

    out = []
    for it in items:
        body = REF_ITEM.sub("", it).strip()
        if len(body) < 12:
            continue
        year = re.search(r"(19|20)\d{2}", body)
        arxiv = re.search(r"arxiv[:\s/]*([0-9]{4}\.[0-9]{4,5})(v\d+)?", body, re.IGNORECASE)
        quotes = re.findall(r"[“\"']([^”\"']{12,200})[”\"']", body)
        if quotes:
            title = quotes[0]
        else:
            title = ""
            # 优先：年份后紧跟的标题（ACL/NAACL 风格 "2018. Contextual string embeddings ...")
            m_year = re.search(r"(19|20)\d{2}[a-z]?\.\s+", body)
            if m_year:
                tail = body[m_year.end():]
                nxt = re.search(r"\.\s+(In |Proceedings|Journal|Trans|arXiv|Adv|Conf|Workshop|Association)", tail)
                title = tail[: nxt.start()] if nxt else tail.split(". ")[0]
            if not title or len(title) < 10:
                segs = [s.strip() for s in re.split(r"\.\s+", body) if s.strip()]
                if len(segs) >= 2:
                    cand = segs[1]
                    if len(cand) < 12 and len(segs) >= 3:
                        cand = max(segs[1:3], key=len)
                    title = cand

        authors = body.split(",")[0][:120] if "," in body else body[:80]
        out.append({
            "raw": it[:420],
            "title": re.sub(r"\s+", " ", title)[:200],
            "authors": authors,
            "year": year.group(0) if year else "",
            "arxiv_id": arxiv.group(1) if arxiv else "",
        })
    return out



def _guess_year(doc, page1_text: str, blocks: list[dict]) -> str:
    # arXiv 编号前四位 YYMM 最可靠（v1 原始年份）
    m = re.search(r"arxiv:\s*(\d{2})(\d{2})\.", page1_text, re.I)
    if m:
        yy = int(m.group(1))
        return str(2000 + yy if yy < 90 else 1900 + yy)
    meta = doc.metadata or {}
    for key in ("creationDate", "modDate"):
        v = meta.get(key, "")
        mm = re.match(r"D:(\d{4})", v or "")
        if mm and 1990 <= int(mm.group(1)) <= 2030:
            return mm.group(1)
    years = re.findall(r"\b(20[0-2]\d|19[9]\d)\b", page1_text)
    if years:
        return Counter(years).most_common(1)[0][0]
    return ""



def parse_pdf(path: str | Path) -> dict[str, Any]:
    doc = fitz.open(str(path))
    n_pages = doc.page_count
    pages: list[dict] = []
    raw_blocks: list[dict] = []
    font_counter: Counter = Counter()
    tables: list[dict] = []
    figures: list[dict] = []

    for pno in range(n_pages):
        page = doc[pno]
        pw, ph = page.rect.width, page.rect.height
        d = page.get_text("dict")
        blocks = []
        for b in d.get("blocks", []):
            if b.get("type") != 0:
                continue
            text = _block_text(b)
            if not text:
                continue
            size, bold = _block_font(b)
            for line in b.get("lines", []):
                for s in line.get("spans", []):
                    if s.get("text", "").strip():
                        font_counter[round(float(s.get("size", 0)), 1)] += len(s["text"])
            bb = [round(v, 1) for v in b["bbox"]]
            blocks.append({"bbox": bb, "text": text, "size": size, "bold": bold, "page": pno + 1})
        ncol = _detect_columns(blocks, pw)
        ordered = _read_order(blocks, ncol, pw)
        for blk in ordered:
            blk["ncol"] = ncol
        raw_blocks.extend(ordered)
        pages.append({"n": pno + 1, "w": round(pw, 1), "h": round(ph, 1), "columns": ncol,
                      "blocks": [{"bbox": b["bbox"], "text": b["text"], "size": b["size"]} for b in ordered]})

        try:
            for t in page.find_tables().tables:
                rows = t.extract()
                cells = [[(c or "").strip() for c in row] for row in rows if row]
                if sum(1 for row in cells for c in row if c) < 3:
                    continue
                tables.append({"page": pno + 1, "bbox": [round(v, 1) for v in t.bbox], "rows": cells})
        except Exception:
            pass

        try:
            for img in page.get_images(full=True):
                rects = page.get_image_rects(img[0])
                if not rects:
                    continue
                r = rects[0]
                if r.width * r.height < 20000:
                    continue
                cap = ""
                for blk in ordered:
                    if r.y1 - 4 <= blk["bbox"][1] <= r.y1 + 80 and FIG_CAP.match(blk["text"]):
                        cap = blk["text"][:300]
                        break
                figures.append({"page": pno + 1, "bbox": [round(v, 1) for v in (r.x0, r.y0, r.x1, r.y1)], "caption": cap})
        except Exception:
            pass

    body_size = font_counter.most_common(1)[0][0] if font_counter else 10.0
    raw_blocks = _merge_number_headings(raw_blocks)
    page1_blocks = [b for b in raw_blocks if b["page"] == 1]
    page1_text = "\n".join(b["text"] for b in page1_blocks[:40])
    meta_title = _norm((doc.metadata or {}).get("title") or "")
    title = _guess_title(page1_blocks, body_size, pages[0]["h"] if pages else 800, meta_title) if page1_blocks else meta_title
    if meta_title and len(meta_title) > 8 and (not title or len(title) < 8 or ARXIV_STAMP.match(title)):
        title = meta_title
    # 组成标题的块（含被折行的标题第二行）在结构解析里要跳过
    title_norm = re.sub(r"\s+", " ", title).strip().lower()
    skip_blocks: set[tuple] = set()
    for b in page1_blocks:
        t = re.sub(r"\s+", " ", b["text"]).strip().lower()
        if t and (t in title_norm or ARXIV_STAMP.match(b["text"].strip())):
            skip_blocks.add((b["page"], tuple(b["bbox"])))
    # 摘要起始位置：避免把标题/作者当正文
    abs_idx = None
    for i, b in enumerate(raw_blocks):
        if b["text"].strip().lower().strip(" :.") in ("abstract", "摘要"):
            abs_idx = i
            break

    refs_start, refs_end = _find_refs_section(raw_blocks)

    outline: list[dict] = []
    chunks: list[dict] = []
    abstract_parts: list[str] = []
    ref_text_parts: list[str] = []
    cur_section = "Body"

    for idx, blk in enumerate(raw_blocks):
        txt = blk["text"]
        if (blk["page"], tuple(blk["bbox"])) in skip_blocks:
            continue
        if refs_start >= 0 and refs_start <= idx < refs_end:
            ref_text_parts.append(txt)
            continue
        if abs_idx is not None and idx < abs_idx:
            continue  # 标题、作者、机构、注脚
        level = heading_level(txt, blk["size"], body_size, blk["bold"])
        if level:
            title_line = re.sub(r"\s+", " ", txt).strip()
            outline.append({"level": level, "title": title_line, "page": blk["page"], "id": f"h{len(outline)}"})
            cur_section = title_line
            continue
        if _is_math(txt) and len(txt) < 220:
            chunks.append({"page": blk["page"], "section": cur_section, "text": txt, "kind": "formula"})
            continue
        if FIG_CAP.match(txt) and len(txt) < 400:
            chunks.append({"page": blk["page"], "section": cur_section, "text": txt, "kind": "caption"})
            continue
        if abs_idx is not None and idx == abs_idx + 1:
            pass
        if cur_section.lower().startswith(("abstract", "摘要")):
            abstract_parts.append(txt)
        for piece in _split_sentences(txt, CHUNK_MAX_CHARS):
            chunks.append({"page": blk["page"], "section": cur_section, "text": piece, "kind": "text"})

    page1_text = "\n".join(b["text"] for b in page1_blocks[:40])
    meta_title = _norm((doc.metadata or {}).get("title") or "")
    title = _guess_title(page1_blocks, body_size, pages[0]["h"] if pages else 800, meta_title) if page1_blocks else meta_title
    if meta_title and len(meta_title) > 8 and (not title or len(title) < 8 or ARXIV_STAMP.match(title)):
        title = meta_title
    authors = _guess_authors(page1_blocks, title, body_size)
    year = _guess_year(doc, page1_text, page1_blocks)
    abstract = _norm(" ".join(abstract_parts))[:4000]
    if not abstract:
        # 退而求其次：取第一个章节前的首段
        first = next((c["text"] for c in chunks if c["kind"] == "text" and c["page"] == 1), "")
        abstract = first[:2000]
    refs = _parse_refs(ref_text_parts)
    if len(refs) < 3:
        tail_lines = [b["text"] for b in raw_blocks[int(len(raw_blocks) * 0.55):]]
        cand = _parse_refs(tail_lines)
        if len(cand) > len(refs):
            refs = cand

    n_chars = sum(len(c["text"]) for c in chunks)
    meta = {
        "title": title or Path(path).stem,
        "authors": authors,
        "year": year,
        "abstract": abstract,
        "n_pages": n_pages,
        "columns": Counter(p["columns"] for p in pages).most_common(1)[0][0] if pages else 1,
        "n_chunks": len(chunks),
        "n_tables": len(tables),
        "n_figures": len(figures),
        "n_refs": len(refs),
        "n_chars": n_chars,
        "body_font": body_size,
    }
    doc.close()
    return {
        "meta": meta,
        "outline": outline,
        "pages": pages,
        "chunks": chunks,
        "tables": tables,
        "figures": figures,
        "refs": refs,
    }


def content_fingerprint(path: str | Path, head_pages: int = 8) -> tuple[str, list[int]]:
    """返回 (全文归一化 sha256, MinHash 签名) 用于内容去重。"""
    doc = fitz.open(str(path))
    texts = [doc[i].get_text("text") for i in range(min(head_pages, doc.page_count))]
    doc.close()
    norm = re.sub(r"\s+", " ", _norm("\n".join(texts))).lower()
    sha = hashlib.sha256(norm.encode("utf-8")).hexdigest()

    import random
    words = re.findall(r"[\w\u4e00-\u9fff]+", norm)
    shingles = {" ".join(words[i:i + 5]) for i in range(max(len(words) - 4, 1))}
    rnd = random.Random(20260101)
    a = [rnd.randint(1, 2 ** 31 - 1) for _ in range(64)]
    b = [rnd.randint(0, 2 ** 31 - 1) for _ in range(64)]
    sig = [2 ** 31] * 64
    for s in shingles:
        h = int(hashlib.md5(s.encode()).hexdigest(), 16)
        for k in range(64):
            v = (a[k] * h + b[k]) % 2147483647
            if v < sig[k]:
                sig[k] = v
    return sha, sig


def minhash_similarity(sig_a: list[int], sig_b: list[int]) -> float:
    if not sig_a or not sig_b or len(sig_a) != len(sig_b):
        return 0.0
    return sum(1 for x, y in zip(sig_a, sig_b) if x == y) / len(sig_a)
