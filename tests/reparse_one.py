"""只重解析指定 paper id。用法：python tests/reparse_one.py 2"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import pipeline  # noqa: E402
from app.db import exec_, one  # noqa: E402
from app.parser import parse_pdf  # noqa: E402

pid = int(sys.argv[1])
row = one("SELECT id, path, filename, n_pages FROM papers WHERE id=?", (pid,))
pdf = Path(row["path"])
struct = parse_pdf(pdf)
meta = struct["meta"]
exec_("DELETE FROM chunks WHERE paper_id=?", (pid,))
exec_("DELETE FROM refs WHERE paper_id=?", (pid,))
for i, c in enumerate(struct["chunks"]):
    exec_("INSERT INTO chunks(paper_id,page,section,ordinal,text) VALUES(?,?,?,?,?)",
          (pid, c["page"], c["section"], i, c["text"]))
for r in struct["refs"]:
    exec_("INSERT INTO refs(paper_id,raw,title,authors,year,arxiv_id) VALUES(?,?,?,?,?,?)",
          (pid, r["raw"], r["title"], r["authors"], r["year"], r["arxiv_id"]))
exec_("UPDATE papers SET n_pages=?, n_chars=?, meta_json=? WHERE id=?",
      (meta["n_pages"], meta["n_chars"], json.dumps(meta, ensure_ascii=False), pid))
pipeline.save_struct(pid, struct)
print(f"#{pid} {row['filename']} 块 {len(struct['chunks'])} 引用 {meta['n_refs']} 页 {meta['n_pages']}")
