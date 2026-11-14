"""用最新解析器重解析库内所有 PDF，覆盖 chunks/refs 与结构缓存（保留论文 id 与图谱关系）。
用法：.venv\\Scripts\\python.exe tests\\reparse.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import pipeline  # noqa: E402
from app.db import exec_, q  # noqa: E402
from app.parser import parse_pdf  # noqa: E402

for row in q("SELECT id, path, filename, n_pages FROM papers ORDER BY id"):
    pdf = Path(row["path"])
    if not pdf.exists():
        print(f"# {row['id']} 跳过：PDF 不存在 {pdf}")
        continue
    struct = parse_pdf(pdf)
    meta = struct["meta"]
    exec_("DELETE FROM chunks WHERE paper_id=?", (row["id"],))
    exec_("DELETE FROM refs WHERE paper_id=?", (row["id"],))
    for i, c in enumerate(struct["chunks"]):
        exec_("INSERT INTO chunks(paper_id,page,section,ordinal,text) VALUES(?,?,?,?,?)",
              (row["id"], c["page"], c["section"], i, c["text"]))
    for r in struct["refs"]:
        exec_("INSERT INTO refs(paper_id,raw,title,authors,year,arxiv_id) VALUES(?,?,?,?,?,?)",
              (row["id"], r["raw"], r["title"], r["authors"], r["year"], r["arxiv_id"]))
    exec_("UPDATE papers SET n_pages=?, n_chars=?, meta_json=? WHERE id=?",
          (meta["n_pages"], meta["n_chars"], json.dumps(meta, ensure_ascii=False), row["id"]))
    pipeline.save_struct(row["id"], struct)
    pages = sorted({c["page"] for c in struct["chunks"]})
    print(f"# {row['id']} {row['filename'][:34]:34s} 页 {row['n_pages']}->{meta['n_pages']} "
          f"块 {len(struct['chunks']):4d}(覆盖页 {pages[0]}-{pages[-1]}) 引用 {meta['n_refs']}")

from app.search import INDEX  # noqa: E402
INDEX.version = -1
print("索引已失效，重启服务后自动重建。")
