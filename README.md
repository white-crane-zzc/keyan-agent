# 科研小助手 Agent

面向科研阅读全流程的本地 Web 应用：PDF 解析 → 内容去重 → 单篇/多篇 RAG 问答（带原文引用）→ 双栏阅读与对照翻译 → 论文自动下载与推荐 → 引用图谱与综述 → 写作助手。

纯本地运行，数据全部落在项目目录内（`data/`），不依赖任何云服务；大模型为**可插拔的 OpenAI 兼容接口**，不填 key 时自动降级为「原文证据模式」，功能不中断。

## 交付物

| 交付项 | 位置 |
|---|---|
| 代码仓库 | `E:\项目\科研小助手`（Git 仓库，分支 `main`，6 条提交记录） |
| 技术文档（PDF，5 页） | `docs\技术文档.pdf`（源文件 `docs\技术文档.md`，生成脚本 `docs\make_pdf.py`） |
| 演示视频（1080p，5 分 02 秒） | `docs\演示视频.mp4`（由 `tests\demo_video.py` 驱动真实界面生成） |
| 环境配置 | `requirements.txt`、`启动.cmd`、`run.ps1`、`.env.example` |
| 在线演示 | 本地运行在 `http://127.0.0.1:8000`；公网演示需部署到有公网入口的机器 |

## 自测脚本

| 脚本 | 作用 |
|---|---|
| `tests/fetch_pdfs.py` | 下载自测论文到 `data/pdf/`（仓库不提交 PDF） |
| `tests/e2e_test.py` | 接口级 10 步：上传/去重/结构/问答/图谱/渲染/翻译 |
| `tests/ui_check.py` | CDP 逐页签截图，收集控制台异常 |
| `tests/ui_flow.py` | 真实点击提问、生成图谱、生成框架、抓取推荐并断言输出 |
| `tests/demo_video.py` | 采集真实界面截图 + 推镜 + 字幕，输出 `docs\演示视频.mp4` |
| `tests/reparse.py` / `reparse_one.py` | 解析器改动后重解析全库 / 单篇 |
| `tests/ingest_folder.py` | 批量入库一个目录下的 PDF（自动跳过重复） |
| `tests/scanned_check.py` | 合成 4 页扫描件并验证离线 OCR 解析 |
| `tests/ui_reader_card.py` | 阅读页专项：正文 [n] 跳参考文献、返回正文、中英对照联动 |
| `tests/req_bench.py` | 需求文档 9 道样例题批量实测 + 图谱导出 |

## 功能对照

| 需求条目 | 实现 | 入口 |
|---|---|---|
| 1.1.1 内容去重（版本差异对比、提示保留新版） | 标题+摘要+MinHash 综合判重，返回相似度、逐项差异（页数/字符/参考/图表/章节增删）与保留建议 | 上传 PDF |
| 1.1.2 细粒度解析 | 标题、作者、摘要、一~三级标题树、表格、图、参考文献、附录；单栏/双栏自动识别；无文本层页面自动走离线 OCR | `app/parser.py` |
| 1.2.1 单篇问答（RAG + 原文引用） | BM25 检索 + 上下文编号 + 页码引用，未配置模型时直接给证据 | 问答页 |
| 1.2.2 多篇对比问答 | 跨论文检索，引用标注论文名+页码 | 问答页（多选） |
| 1.3.1 双栏/单栏阅读、公式表格排版 | 按 PyMuPDF 文本块 bbox 还原双栏，公式与表格以原始 PDF 渲染保留 | 阅读页 |
| 1.3.2 树状导航 + 引用跳转/跳回 | 章节树点击定位；正文 `[n]` 上标 → 左栏参考文献高亮 → 「返回正文」回到原页原位置 | 阅读页 |
| 1.3.3 部分/整篇/中英对照翻译 | 划词翻译、整页/按页翻译、中英对照左右滚动联动；代码公式块跳过；翻译缓存入库 | 阅读页 |
| 1.4.1 按名称自动下载入库、参考文献批量下载 | arXiv API 检索下载入库；`/api/refs/batch` 按正文引用次数筛「保留/存疑」并批量下载候选 | 文库页 |
| 1.4.2 定期刷新 arXiv | 服务启动即后台线程每 6 小时拉取（`RECOMMEND_REFRESH_HOURS` 可调），结果落库 | 自动 / 推荐页 |
| 1.4.3 每日/每周推荐（理由、github 优先、赞踩） | 相关性打分 + 推荐理由 + has_code 标记 + 点赞/踩反馈落库 | 推荐页 |
| 1.5 引用图谱、核心节点挖掘、综述、未来工作 | PageRank 找基石/边缘论文；`/api/survey`、`/api/futurework` 抽取结论/未来工作段落 | 图谱页 |
| 1.6 写作助手（框架、架构图、CSV 可视化） | 框架生成（References 只取库内真实文献）；Mermaid/TikZ/Graphviz 架构图；CSV → 折线/柱状/雷达 + 学术图注 + 趋势结论 | 写作页 |
| 1.3.3 重排导出 | `/api/papers/{pid}/export?fmt=md|html`，按章节重排（摘要→各章→参考文献） | 阅读页 |
| 3.1 代码仓库 | 本仓库 + README + 环境说明 + Git 历史 | 仓库根目录 |
| 3.5 敏感信息 | 全部走 `.env`，仓库只提交 `.env.example` | `.gitignore` |

## 快速开始

```powershell
# 1. 创建环境并装依赖（Python 3.10+）
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install fastapi "uvicorn[standard]" python-multipart pymupdf numpy networkx httpx matplotlib pandas rapidocr-onnxruntime

# 2. 启动
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 3. 浏览器打开
start http://127.0.0.1:8000
```

Windows 下也可直接双击 `启动.cmd`（自动建环境、装依赖、起服务）。

## 配置大模型（可选）

```powershell
Copy-Item .env.example .env
# 编辑 .env：
#   LLM_BASE_URL / LLM_API_KEY / LLM_MODEL   任意 OpenAI 兼容服务（豆包、DeepSeek、通义、Kimi、OpenAI）
#   或本地 Ollama：LLM_BASE_URL=http://localhost:11434/v1  LLM_API_KEY=ollama  LLM_MODEL=qwen2.5:7b
```

重启服务后顶栏会从「未配置大模型」变为模型名。不配置时：问答返回检索到的原文证据（仍带页码引用），翻译接口返回 `degraded: true`，其余功能不受影响。

## 目录结构

```
科研小助手/
├─ app/
│  ├─ config.py    # 路径、参数、.env 读取、llm_ready()
│  ├─ db.py        # SQLite（papers/chunks/refs/translations/recs）
│  ├─ parser.py    # PyMuPDF 解析：标题/作者/章节层级/双栏/表格/图/参考文献
│  ├─ pipeline.py  # 入库、去重判定、版本差异、删除
│  ├─ search.py    # BM25 + 中文二元组索引，引用上下文拼装
│  ├─ llm.py       # OpenAI 兼容调用：问答/翻译/综述/未来工作/框架/架构图/图注
│  ├─ graph.py     # 引用图谱、PageRank、综述素材抽取
│  ├─ arxiv.py     # arXiv 下载/检索/推荐/反馈
│  └─ main.py      # REST 路由
├─ static/         # 六页签前端（文库/阅读/问答/图谱/写作/推荐）
├─ data/           # pdf、解析索引、页面渲染、图表、SQLite（不入库）
├─ tests/          # e2e_test.py（接口级）、ui_flow.py（浏览器交互级）
├─ docs/           # 技术文档
└─ 启动.cmd / run.ps1 / .env.example / requirements.txt
```

## 主要接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/status` | 服务与模型状态、库统计 |
| GET/POST | `/api/papers`、`/api/upload` | 文库列表、批量上传（`on_duplicate=ask/keep_both/replace`） |
| POST | `/api/upload/confirm` | 去重确认：`keep_new/keep_both/cancel` |
| POST | `/api/ingest/arxiv` | `{ids:[...]}` 或 `{query,max}` 下载入库 |
| GET | `/api/papers/{id}/struct` | 结构树、表格、图、参考文献 |
| GET | `/api/papers/{id}/page/{n}` | 页面文本块（bbox）+ 渲染图 |
| POST | `/api/ask` | 单篇/多篇 RAG 问答，返回 answer + citations |
| POST | `/api/translate`、`/api/translate/range` | 划词/整页翻译 |
| POST | `/api/graph` | 引用图谱、核心/边缘论文、外部高频引用 |
| POST | `/api/survey`、`/api/futurework` | 自动综述、未来工作 |
| POST | `/api/write/outline`、`/api/write/diagram` | 论文框架、架构图（mermaid/tikz/graphviz） |
| POST | `/api/plot` | CSV → 折线/柱状/雷达 + 图注 |
| POST | `/api/recommend`、`/api/feedback` | arXiv 推荐、赞踩反馈 |

## 实测结果（本机自测）

- 解析：Attention（15 页/单栏/40 条参考文献/24 章节）、BERT（16 页/双栏/59 条/25 章节）标题、年份、层级全部正确。
- 分块覆盖：参考文献之后若还有附录，继续按正文入库（不再把附录当参考文献丢掉）；首页作者/单位与每条参考文献也单独建块。Attention 461 块、BERT 388 块，全库 27 篇 22217 块 / 2369 条参考文献。
- 检索：中文提问命中英文原文——术语词表 + 模型检索式 + 模型重排三层，问「多头注意力每头维度」可定位到 3.2.2 并答出 h=8、d_k=d_v=64；问「第6作者是谁、在哪家公司」答出 Aidan N. Gomez / University of Toronto；问「引用的 Layer Normalization 文献」答出 Ba、Kiros、Hinton 2016；多篇对比按篇配额召回。
- 去重：同一篇 v1 与 v7（版面不同、v7 首页多授权声明）判定为重复，相似度 **0.954**，差异对比与「保留库内版本」建议均正常；`keep_both` 可并存。
- 大模型：DeepSeek `deepseek-chat` 实测可用（问答 1.8-3.5s、翻译 0.9s、论文框架 5.7s、综述/未来工作 2-7s）；填占位串时自动判定为未配置，退回证据模式。
- 问答、多篇问答、图谱（3 节点 1 边，基石=Attention）、页面渲染（2 栏 13 块/497KB PNG）、CSV 绘图、推荐（8 条）均通过。
- 前端六页签真实点击验证通过，无 JS 异常（`tests/ui_flow.py`）。

## 已知限制

- 扫描版 PDF 走文本层，无 OCR 时解析为空，需接 OCR（未接）。
- 公式为 PDF 渲染图，未做 LaTeX 抽取。
- 「超参数表/数值型」问题召回仍不稳：表格已单独入块并可检索，但中文问「超参数设置」或问表格里单个数字（如被超越模型的 26.36 BLEU）时仍可能被判定为「材料未提及」，需继续加语义检索或人工核对原文页码。
- 大模型未配置时，问答/翻译/综述只输出检索证据，不做生成。
- 引用图谱依赖参考文献标题匹配，中文/无编号格式的参考文献匹配率低于英文标准格式。

## 团队与许可

本地竞赛用实现，代码为自研；第三方库版权归各自作者（PyMuPDF、FastAPI、networkx、matplotlib 等）。
