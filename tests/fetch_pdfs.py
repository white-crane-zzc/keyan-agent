"""下载自测用论文到 data/pdf/（仓库不提交 PDF 二进制）。
用法：python tests/fetch_pdfs.py
"""
import urllib.request
from pathlib import Path

PDF = Path(r"E:\项目\科研小助手\data\pdf")
PDF.mkdir(parents=True, exist_ok=True)

ITEMS = {
    "1706.03762v7.pdf": "https://arxiv.org/pdf/1706.03762v7",
    "1706.03762v1.pdf": "https://arxiv.org/pdf/1706.03762v1",
    "1810.04805_BERT.pdf": "https://arxiv.org/pdf/1810.04805",
}

for name, url in ITEMS.items():
    dst = PDF / name
    if dst.exists():
        print("已存在:", name)
        continue
    print("下载:", url)
    with urllib.request.urlopen(url, timeout=120) as r:
        dst.write_bytes(r.read())
    print("  完成:", name, dst.stat().st_size // 1024, "KB")
