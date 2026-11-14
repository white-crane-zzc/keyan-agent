"""图谱 / 写作四类能力真机接口验收。"""
import io

import httpx

BASE = "http://127.0.0.1:8000"
ids = [1, 3, 27, 28, 8]

g = httpx.post(f"{BASE}/api/graph", json={"paper_ids": ids}, timeout=120).json()
print("图谱: 节点", len(g["nodes"]), "边", len(g["edges"]),
      "基石", len(g["core"]), "边缘", len(g["peripheral"]), "外部", len(g["external_top"]))
print("  前三个:", [(n["title"][:28], n["role"], n["in"]) for n in g["nodes"][:3]])

o = httpx.post(f"{BASE}/api/write/outline",
               json={"idea": "用稀疏注意力降低长文本推理成本", "paper_ids": ids}, timeout=180).json()
print("框架: 字数", len(o.get("text", "")), "参考文献", len(o.get("refs", [])))
print("  开头:", (o.get("text") or "").replace("\n", " ")[:120])

for kind in ("mermaid", "tikz", "graphviz"):
    d = httpx.post(f"{BASE}/api/write/diagram",
                   json={"desc": "输入→分词→编码器堆叠→分类头", "kind": kind}, timeout=180).json()
    first = (d.get("text") or "").splitlines()[0]
    print(f"架构图 {kind}: 首行 {first[:40]} 长度 {len(d.get('text',''))}")

csv = "模型,BLEU,参数量\nTransformer,28.4,65\nBERT,31.0,110\nGPT-2,29.0,1542\n".encode()
r = httpx.post(f"{BASE}/api/plot", files={"file": ("bench.csv", csv, "text/csv")},
               data={"desc": "不同模型 BLEU 对比", "kind": "bar"}, timeout=180)
print("CSV 柱状图:", r.status_code, r.json().get("image"), "|", (r.json().get("caption") or "")[:60])
print("  统计:", r.json().get("stats"))

xlsx = io.BytesIO()
import openpyxl
wb = openpyxl.Workbook()
ws = wb.active
ws.append(["Epoch", "Accuracy"])
for row in [(1, 0.72), (2, 0.81), (3, 0.87)]:
    ws.append(row)
wb.save(xlsx)
r2 = httpx.post(f"{BASE}/api/plot", files={"file": ("train.xlsx", xlsx.getvalue(),
               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                data={"desc": "训练准确率", "kind": "line"}, timeout=180)
print("XLSX 折线图:", r2.status_code, r2.json().get("image"))
