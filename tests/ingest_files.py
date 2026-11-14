"""按文件名精确入库少量 PDF。用法：python tests/ingest_files.py a.pdf b.pdf"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import pipeline  # noqa: E402
from app.search import INDEX  # noqa: E402

for name in sys.argv[1:]:
    p = Path(name)
    if not p.exists():
        print(f"[缺失] {p}")
        continue
    r = pipeline.ingest(p, p.name, on_duplicate="ask")
    if r.get("status") == "duplicate":
        print(f"[跳过] {p.name} 重复 #{r.get('existing', {}).get('id')}")
    elif r.get("status") == "ingested":
        m = r["meta"]
        print(f"[入库] #{r['id']} {p.name} {m['year']} {m['n_pages']}页 {m['n_chunks']}块 {m['n_refs']}参考")
    else:
        print(f"[?] {p.name} {r.get('status')}")

INDEX.version = -1
