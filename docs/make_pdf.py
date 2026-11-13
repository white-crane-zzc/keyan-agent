"""技术文档 md → HTML → PDF（无头 Edge 打印）。用法：python docs/make_pdf.py"""
import subprocess
import sys
from pathlib import Path

import markdown

ROOT = Path(r"E:\项目\科研小助手")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

md_path = ROOT / "docs" / "技术文档.md"
html_path = ROOT / "docs" / "技术文档.html"
pdf_path = ROOT / "docs" / "技术文档.pdf"

body = markdown.markdown(
    md_path.read_text(encoding="utf-8"),
    extensions=["tables", "fenced_code", "toc", "sane_lists"],
)

CSS = """
@page { size: A4; margin: 18mm 16mm; }
body { font-family: "Microsoft YaHei", "PingFang SC", sans-serif; font-size: 10.5pt;
       line-height: 1.65; color: #1f2430; }
h1 { font-size: 19pt; border-bottom: 2px solid #2f6fed; padding-bottom: 6px; margin: 0 0 14px; }
h2 { font-size: 13.5pt; margin-top: 22px; color: #2f6fed; page-break-after: avoid; }
h3 { font-size: 11.5pt; margin-top: 16px; page-break-after: avoid; }
table { border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 9.5pt; page-break-inside: avoid; }
th, td { border: 1px solid #d6dce8; padding: 5px 8px; text-align: left; vertical-align: top; }
th { background: #eef2fa; }
code { background: #f3f5f9; padding: 1px 4px; border-radius: 3px; font-size: 9pt; }
pre { background: #f6f7fa; border-left: 3px solid #2f6fed; padding: 9px 12px; overflow-x: auto; font-size: 8.8pt;
      line-height: 1.45; page-break-inside: avoid; }
hr { border: none; border-top: 1px solid #e3e8f1; margin: 18px 0; }
li { margin: 3px 0; }
"""

html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>科研小助手 Agent 技术文档</title><style>{CSS}</style></head><body>{body}</body></html>"""

html_path.write_text(html, encoding="utf-8")
print("HTML 已生成:", html_path)

subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                f"--print-to-pdf={pdf_path}", html_path.as_uri()],
               check=False, timeout=120, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

if pdf_path.exists():
    print("PDF 已生成:", pdf_path, pdf_path.stat().st_size, "字节")
else:
    print("PDF 生成失败")
    sys.exit(1)
