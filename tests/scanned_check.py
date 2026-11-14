"""生成扫描件样本并验证 OCR 解析（对应需求 1.1.2 / 测试数据第 2 条）。"""
import sys
import time
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fitz
from PIL import Image

from app.parser import parse_pdf

SRC = r"E:\项目\科研小助手\data\pdf\1706.03762v1.pdf"
OUT = Path(r"E:\项目\科研小助手\data\demo\1706.03762v1_img.pdf")

OUT.parent.mkdir(parents=True, exist_ok=True)
src = fitz.open(SRC)
new = fitz.open()
for pno in range(min(4, src.page_count)):
    pix = src[pno].get_pixmap(dpi=150)
    img = Image.open(BytesIO(pix.tobytes("png"))).convert("RGB")
    tmp = OUT.parent / f"_scan_{pno}.jpg"
    img.save(tmp, quality=85)
    pdf_bytes = fitz.open()
    rect = fitz.Rect(0, 0, img.width * 72 / 150, img.height * 72 / 150)
    page = pdf_bytes.new_page(width=rect.width, height=rect.height)
    page.insert_image(rect, filename=str(tmp))
    new.insert_pdf(pdf_bytes)
    pdf_bytes.close()
new.save(str(OUT))
new.close()
print(f"扫描件已生成 {OUT} 大小 {(OUT.stat().st_size // 1024)} KB")

t0 = time.time()
struct = parse_pdf(OUT)
m = struct["meta"]
print(f"解析耗时 {time.time() - t0:.1f}s")
print("标题:", m["title"][:70])
print("年份:", m["year"], "页:", m["n_pages"], "块:", m["n_chunks"], "OCR 页:", m.get("n_ocr_pages"))
print("作者:", (m["authors"] or "")[:80])
print("摘要:", (m["abstract"] or "")[:200])
print("章节:", [h["title"][:26] for h in struct["outline"][:6]])
