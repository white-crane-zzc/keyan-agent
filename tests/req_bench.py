"""按需求文档 1.2 的 9 道样例题跑真实问答，输出答案与引用，用于人工判分。"""
import json
import time

import httpx

C = httpx.Client(base_url="http://127.0.0.1:8000", timeout=300)

ATT = 1   # Attention v7
BERT = 3
GPT1, GPT2, GPT3 = 27, 28, 8

CASES = [
    ("单篇", "论文 Attention Is All You Need 的第6作者是谁，在哪个公司/机构工作？", [ATT]),
    ("单篇", "这篇论文里 Adam 优化器的超参数 β1 和 β2 分别设置成了多少？", [ATT]),
    ("单篇", "这篇论文的 Transformer 架构在训练 Base 模型时用了多少个 GPU？具体是什么型号？", [ATT]),
    ("单篇", "Transformer (big) 模型在 English-to-German 任务上的 BLEU 分数是多少？当时的 State-of-the-art 模型是多少？提升了多少？", [ATT]),
    ("单篇", "请列出论文中引用的关于 Layer Normalization 的参考文献的完整作者和年份。", [ATT]),
    ("多篇", "对比《Attention Is All You Need》与 BERT 论文：BERT 的架构和原始 Transformer 的 Encoder 是什么继承关系？BERT 丢弃了原始 Transformer 的哪个部分？", [ATT, BERT]),
    ("多篇", "对比 GPT-1、GPT-2 和 GPT-3 的论文，说明这些模型的参数量的变化。", [GPT1, GPT2, GPT3]),
    ("多篇", "GPT-2 相比 GPT-1，在 Transformer 的 Layer Normalization 位置上做了什么关键调整？", [GPT1, GPT2]),
    ("多篇", "从 GPT-1 到 GPT-3，模型的最大上下文 Token 长度（Context Window）分别递增到了多少？", [GPT1, GPT2, GPT3]),
]

for i, (kind, q, ids) in enumerate(CASES, 1):
    t0 = time.time()
    r = C.post("/api/ask", json={"question": q, "paper_ids": ids}).json()
    ans = (r.get("answer") or "").replace("\n", " ")
    cits = [(c["paper_id"], c["page"]) for c in r.get("citations", [])][:6]
    print(f"\n===== {i}. [{kind}] {q}")
    print(f"耗时 {time.time() - t0:.1f}s 引用 {len(r.get('citations', []))} {cits}")
    print(ans[:700])

print("\n\n===== 图谱（全部论文） =====")
g = C.post("/api/graph", json={}).json()
print("节点", len(g.get("nodes", [])), "边", len(g.get("edges", [])))
for n in sorted(g.get("nodes", []), key=lambda x: -x.get("pagerank", 0))[:5]:
    print(" ", n.get("title", "")[:50], "rank=%.4f" % n.get("pagerank", 0), n.get("role"))
json.dump(g, open(r"E:\项目\科研小助手\data\graph_all.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
