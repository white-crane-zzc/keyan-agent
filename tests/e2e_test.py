"""端到端自测：上传/去重/检索/问答/图谱/页面渲染。用法：python tests/e2e_test.py"""
import json
import sys
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
PDF = Path(r"E:\项目\科研小助手\data\pdf")


def show(title):
    print("\n==== " + title + " ====")


def main():
    c = httpx.Client(base_url=BASE, timeout=300)

    show("1. 上传 1706.03762v7")
    r = c.post("/api/upload", files=[("files", ("1706.03762v7.pdf", (PDF / "1706.03762v7.pdf").read_bytes(), "application/pdf"))],
               data={"on_duplicate": "ask"})
    print(json.dumps(r.json(), ensure_ascii=False)[:500])

    show("2. 上传 1706.03762v1（应被判为重复）")
    r = c.post("/api/upload", files=[("files", ("1706.03762v1.pdf", (PDF / "1706.03762v1.pdf").read_bytes(), "application/pdf"))],
               data={"on_duplicate": "ask"})
    j = r.json()["results"][0]
    print("status:", j.get("status"), "| 相似度:", j.get("similarity"))
    if j.get("status") == "duplicate":
        print("建议:", j.get("suggestion"))
        print("差异:", json.dumps(j.get("diff"), ensure_ascii=False))
        # 测试确认并存
        r2 = c.post("/api/upload/confirm", json={"staged": j["staged"], "name": "1706.03762v1.pdf", "action": "keep_both"})
        print("确认并存:", r2.json().get("status"), r2.json().get("id"))

    show("3. 上传 BERT")
    f = PDF / "1810.04805_BERT.pdf"
    if f.exists():
        r = c.post("/api/upload", files=[("files", (f.name, f.read_bytes(), "application/pdf"))],
                   data={"on_duplicate": "ask"})
        j = r.json()["results"][0]
        print("status:", j.get("status"), "| id:", j.get("id"), "|", (j.get("meta") or {}).get("title", "")[:60])

    show("4. 文库列表")
    papers = c.get("/api/papers").json()["papers"]
    for p in papers:
        print(f"  #{p['id']} {p['title'][:52]} | {p['year']} | {p['n_pages']}页 | 段{p['n_chars']} | 参考{p['n_refs']} | {p['columns']}栏")

    show("5. 结构解析")
    pid = papers[0]["id"]
    st = c.get(f"/api/papers/{pid}/struct").json()
    print("outline:", [f"L{o['level']} {o['title'][:26]}" for o in st["outline"][:8]])
    print("表格:", len(st["tables"]), "图:", len(st["figures"]))

    show("6. 单篇问答（无模型时走证据模式）")
    r = c.post("/api/ask", json={"question": "Transformer 用了多少个 attention head？d_model 是多少？", "paper_ids": [pid]})
    j = r.json()
    print("answer:", (j.get("answer") or "")[:400])
    print("citations:", [(x["title"][:20], x["page"]) for x in j.get("citations", [])][:5])

    show("7. 多篇问答")
    r = c.post("/api/ask", json={"question": "这些论文的 Layer Normalization 分别怎么用？"})
    j = r.json()
    print("citations:", [(x["title"][:28], x["page"]) for x in j.get("citations", [])][:6])

    show("8. 引用图谱")
    g = c.post("/api/graph", json={}).json()
    print("节点:", len(g["nodes"]), "边:", len(g["edges"]))
    for n in g["nodes"][:6]:
        print(f"  {n['title'][:40]} 被引{n['in']} 引出{n['out']} 角色{n['role']}")

    show("9. 页面渲染")
    r = c.get(f"/api/papers/{pid}/page/2")
    j = r.json()
    print("页:", j["n"], "/", j["total_pages"], "| 文本块:", len(j["blocks"]), "| 栏:", j["columns"])
    img = c.get(j["image"])
    print("图片字节:", len(img.content), "| content-type:", img.headers.get("content-type"))

    show("10. 翻译（无模型）")
    r = c.post("/api/translate", json={"text": "Attention is all you need."})
    print(r.json())

    print("\n结论：以上各步若均无异常，即端到端可用。")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("测试中断:", type(e).__name__, e)
        sys.exit(1)
