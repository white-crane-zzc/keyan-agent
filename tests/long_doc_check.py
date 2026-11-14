"""长文档规模压测：541 页量级（15 页 Attention 循环拼接 36 份 = 540 页）。
官方《Understanding Deep Learning》PDF 因 GitHub 下载链路被重置未能落盘，
这里用同规模文档验证「页数百级别」时的解析耗时、分块与内存占用。
"""
import ctypes
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pymupdf as fitz

from app.parser import parse_pdf

SRC = r"E:\项目\科研小助手\data\pdf\1706.03762v1.pdf"
OUT = Path(r"E:\项目\科研小助手\data\demo\long_540.pdf")


def rss_mb():
    class PMC(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
    pmc = PMC()
    pmc.cb = ctypes.sizeof(PMC)
    ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
    return pmc.WorkingSetSize // 1048576


src = fitz.open(SRC)
if not OUT.exists():
    doc = fitz.open()
    for _ in range(36):
        doc.insert_pdf(src)
    doc.save(str(OUT))
    doc.close()
print(f"压测文件 {OUT.name} {(OUT.stat().st_size // 1024 // 1024)} MB，页数 {fitz.open(str(OUT)).page_count}")

rss0 = rss_mb()
t0 = time.time()
struct = parse_pdf(OUT)
dt = time.time() - t0
m = struct["meta"]
print(f"解析 {m['n_pages']} 页耗时 {dt:.1f}s（{dt / m['n_pages']:.2f}s/页）")
print(f"字符 {m['n_chars']} 块 {m['n_chunks']} 章节 {len(struct['outline'])} 参考文献 {m['n_refs']}")
print(f"内存 {rss0} MB → {rss_mb()} MB")
