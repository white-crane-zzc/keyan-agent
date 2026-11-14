"""把 E:\\项目\\论文 目录里的 PDF 批量入库。
重复的（同一篇不同版本）跳过，只保留库内已有版本；其余全部解析入库。
用法：.venv\\Scripts\\python.exe tests\\ingest_folder.py [目录]
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import pipeline  # noqa: E402
from app.search import INDEX  # noqa: E402

folder = Path(sys.argv[1] if len(sys.argv) > 1 else r"E:\项目\论文")
pdfs = sorted(folder.glob("*.pdf"))
print(f"待处理 {len(pdfs)} 个 PDF，目录 {folder}")

ok = skipped = failed = 0
for p in pdfs:
    t0 = time.time()
    try:
        r = pipeline.ingest(p, p.name, on_duplicate="ask")
    except Exception as e:
        failed += 1
        print(f"[失败] {p.name}: {type(e).__name__} {e}")
        continue
    if r.get("status") == "duplicate":
        skipped += 1
        print(f"[跳过] {p.name} 与库内 #{r.get('existing', {}).get('id')} 重复 "
              f"({r.get('similarity')}) 建议保留 {r.get('suggest')}")
    elif r.get("status") == "ingested":
        ok += 1
        m = r["meta"]
        print(f"[入库] #{r['id']} {p.name[:38]:38s} {m['year']} {m['n_pages']}页 "
              f"{m['n_chunks']}块 {m['n_refs']}参考 {m['columns']}栏 {time.time() - t0:.1f}s")
    else:
        print(f"[?] {p.name}: {r.get('status')}")

INDEX.version = -1
print(f"\n完成：入库 {ok}，跳过重复 {skipped}，失败 {failed}")
