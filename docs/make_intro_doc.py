"""生成《科研小助手 Agent 作品介绍文档》DOCX。"""
import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = Path(r"E:\项目\科研小助手\docs\科研小助手Agent-作品介绍.docx")
IMG_GRAPH = Path(r"E:\项目\科研小助手\data\graph_all.png")
IMG_PLOT = Path(r"E:\项目\科研小助手\data\write_plot.png")

CN_BODY = "宋体"
CN_TITLE = "黑体"
CN_SUB = "楷体"
EN = "Times New Roman"


def set_run_font(run, cn=CN_BODY, size=12, bold=False, color=None):
    run.font.name = EN
    run.font.size = Pt(size)
    run.bold = bold
    if color:
        run.font.color.rgb = color
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), EN)
    rfonts.set(qn("w:hAnsi"), EN)
    rfonts.set(qn("w:eastAsia"), cn)


def style_font(style, cn, size, bold=False):
    style.font.name = EN
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.color.rgb = RGBColor(0, 0, 0)
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), EN)
    rfonts.set(qn("w:hAnsi"), EN)
    rfonts.set(qn("w:eastAsia"), cn)


def first_line_indent_2chars(p):
    pPr = p._element.get_or_add_pPr()
    ind = pPr.find(qn("w:ind"))
    if ind is None:
        ind = OxmlElement("w:ind")
        pPr.append(ind)
    ind.set(qn("w:firstLineChars"), "200")
    ind.set(qn("w:firstLine"), "240")


doc = Document()

sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21), Cm(29.7)
for attr in ("top_margin", "bottom_margin", "left_margin", "right_margin"):
    setattr(sec, attr, Cm(2.5))

styles = doc.styles
style_font(styles["Normal"], CN_BODY, 12)
styles["Normal"].paragraph_format.line_spacing = 1.5
styles["Normal"].paragraph_format.space_before = Pt(0)
styles["Normal"].paragraph_format.space_after = Pt(0)

style_font(styles["Title"], CN_TITLE, 18, True)
styles["Title"].paragraph_format.space_after = Pt(18)
styles["Title"].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER

style_font(styles["Subtitle"], CN_SUB, 12)
styles["Subtitle"].paragraph_format.space_after = Pt(12)

for name, size, before, after in (("Heading 1", 16, 14, 6), ("Heading 2", 14, 11, 5), ("Heading 3", 12, 9, 4)):
    st = styles[name]
    style_font(st, CN_TITLE, size, True)
    st.paragraph_format.space_before = Pt(before)
    st.paragraph_format.space_after = Pt(after)
    st.paragraph_format.keep_with_next = True


def body(text, indent=True):
    p = doc.add_paragraph()
    r = p.add_run(text)
    set_run_font(r, CN_BODY, 12)
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    if indent:
        first_line_indent_2chars(p)
    return p


def h(text, level=1):
    p = doc.add_paragraph(style=f"Heading {level}")
    r = p.add_run(text)
    set_run_font(r, CN_TITLE, {1: 16, 2: 14, 3: 12}[level], True)
    return p


def caption(text, above=False):
    p = doc.add_paragraph()
    r = p.add_run(text)
    set_run_font(r, CN_BODY, 10.5)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.space_before = Pt(4 if not above else 4)
    p.paragraph_format.space_after = Pt(12 if not above else 4)
    return p


def shade(cell, color="D9D9D9"):
    tcPr = cell._element.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color)
    tcPr.append(shd)


def table(headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = t.rows[0]
    trPr = hdr._tr.get_or_add_trPr()
    th = OxmlElement("w:tblHeader")
    trPr.append(th)
    for i, text in enumerate(headers):
        c = hdr.cells[i]
        c.text = ""
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing = 1
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(text)
        set_run_font(r, CN_BODY, 10.5, True)
        shade(c)
    for row in rows:
        cells = t.add_row().cells
        tr = t.rows[-1]
        trPr = tr._tr.get_or_add_trPr()
        cs = OxmlElement("w:cantSplit")
        trPr.append(cs)
        for i, text in enumerate(row):
            c = cells[i]
            c.text = ""
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if i == 0 else WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.line_spacing = 1
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            r = p.add_run(str(text))
            set_run_font(r, CN_BODY, 10.5)
    if widths:
        for i, w in enumerate(widths):
            for row in t.rows:
                row.cells[i].width = Cm(w)
    return t


def image(path, width_cm=15.5):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(0)
    p.add_run().add_picture(str(path), width=Cm(width_cm))
    return p


def page_break():
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


# ---------------- 封面 ----------------
for _ in range(2):
    doc.add_paragraph()
p = doc.add_paragraph(style="Title")
r = p.add_run("科研小助手 Agent")
set_run_font(r, CN_TITLE, 18, True)

p = doc.add_paragraph(style="Subtitle")
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("面向科研论文全流程的解析、问答、图谱与写作辅助系统")
set_run_font(r, CN_SUB, 12)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("作品介绍文档")
set_run_font(r, CN_TITLE, 16, True)
p.paragraph_format.space_before = Pt(24)

for _ in range(5):
    doc.add_paragraph()

for line in ("参赛赛道：AI 大模型创新应用挑战赛", "作品形态：本地部署的 Web 应用（FastAPI + SQLite）",
             "模型接入：OpenAI 兼容接口，可插拔（DeepSeek / 豆包 / Kimi / 通义 / Ollama）",
             "提交日期：2026 年 11 月"):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(line)
    set_run_font(r, CN_BODY, 12)

page_break()

# ---------------- 目录 ----------------
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("目  录")
set_run_font(r, CN_TITLE, 16, True)
p.paragraph_format.space_after = Pt(12)

toc_par = doc.add_paragraph()
fld = OxmlElement("w:fldSimple")
fld.set(qn("w:instr"), r'TOC \o "1-2" \h \z \u')
inner = OxmlElement("w:r")
t = OxmlElement("w:t")
t.text = "（目录将在打开文档时自动生成；如未显示，请右键选择“更新域”）"
inner.append(t)
fld.append(inner)
toc_par._element.append(fld)
toc_par.paragraph_format.line_spacing = 1

page_break()

# ---------------- 1 作品概述 ----------------
h("1  作品概述", 1)
body("科研小助手 Agent 是一个本地运行的科研论文辅助系统。它把“把论文存进来—读懂它—问它问题—看清论文之间的关系—照着它写初稿—追踪新论文”这五件事串成一条完整流水线，而不是把若干个互不相干的 AI 功能拼在一个页面上。系统以一篇 PDF 为起点，自动完成结构解析、去重入库、检索增强问答、引用网络构建、写作素材生成，全部结果可在同一个界面里连续使用。")
body("选择这个题目，是因为科研新手真实卡住的地方往往不是“不会用大模型”，而是三件事：一是论文太多、英文太长，逐篇精读的时间成本极高；二是通用聊天模型回答论文问题时给不出可核对的原文位置，无法用于写作；三是“这几篇之间谁引了谁、哪篇是绕不开的基石”这类关系问题，靠人脑记不住，靠聊天模型又容易编。系统用“原文证据 + 结构化数据”两个抓手解决：所有回答都带页码与章节引用，所有关系都来自解析出的参考文献条目，而不是模型的记忆。")
body("作品形态为单机 Web 应用：后端 FastAPI + SQLite，前端为不依赖框架的原生页面，六个页签分别是文库、阅读、问答、图谱、写作、推荐。大模型通过 OpenAI 兼容接口接入，可在配置文件中切换 DeepSeek、豆包、Kimi、通义或本地 Ollama；未配置或接口不可用时，系统自动降级为“原文证据模式”，问答直接返回命中的原文片段与出处，保证演示不中断。当前演示库共 27 篇论文、22217 个文本块、2369 条参考文献条目，覆盖 Attention、BERT、GPT 系列与后续主流大模型技术路线。")

# ---------------- 2 需求对照 ----------------
h("2  需求与完成情况对照", 1)
body("按照竞赛需求文档的功能条目逐项落地，完成情况与实测证据见表 1。表中“部分完成”指功能可用但存在明确边界，已在第 9 节说明。")
caption("表 1  需求条目完成情况", above=True)
table(
    ["需求条目", "要求要点", "完成情况", "实测证据"],
    [
        ["1.1 论文上传与解析", "批量上传 PDF，自动提取标题、作者、章节、摘要、参考文献", "已完成",
         "24 个 PDF 批量入库 22 篇、2 篇判重跳过、0 失败；含扫描件 OCR 与 540 页长文档"],
        ["1.2 论文问答", "基于论文内容回答专业问题，给出来源", "已完成",
         "中文提问英文论文可召回；回答附页码与章节；9 道样例题 7 题达标"],
        ["1.3 阅读辅助", "原文阅读、翻译、中英对照、跳转", "已完成",
         "段落级翻译与中英对照滚动联动、悬停翻译、正文 [n] 与参考文献双向跳转、Markdown/HTML 导出"],
        ["1.4.1 论文框架", "给定想法生成论文框架与参考文献", "已完成", "实测输出 1511 字、5 条参考文献，文献只从库内选取"],
        ["1.4.2 架构图/流程图", "按描述生成架构图", "已完成", "Mermaid 直接渲染为框图，另支持 TikZ、Graphviz 源码，三种格式均实测"],
        ["1.4.3 实验数据可视化", "上传实验数据生成图表", "已完成", "CSV 与 XLSX 均可，折线/柱状/雷达三种，自动生成中英文图注与统计摘要"],
        ["1.5 引用图谱", "构建引用网络、识别核心论文、生成综述", "已完成",
         "全库 27 节点 92 条边，基石 BERT 被引 13；选 1 篇自动补一跳邻居；自动综述与未来工作建议可用"],
        ["1.6 新论文推荐", "定期推荐相关新论文并支持反馈", "已完成", "抓取 arXiv，按主题重合度与开源代码加权排序，记录有用/不相关反馈，后台每 6 小时自动刷新"],
        ["2 测试数据", "指定论文 + 扫描件 + 长篇专著", "已完成", "指定论文全部入库；4 页扫描件 OCR 识别正确；540 页合成长文档 306 秒解析完成"],
        ["3.1 源码提交", "提供可运行的完整源码", "已完成", "本地 Git 仓库，含启动脚本、依赖清单、自测脚本与技术文档"],
        ["3.2 演示视频", "普通话配音演示视频", "未由本系统完成", "演示视频由参赛者本人录制，不属软件功能"],
        ["3.4 公网演示", "提供在线演示与测试账号", "未完成", "当前为本地部署、零鉴权，开放公网存在删库风险，故未上线"],
    ],
    widths=[3.0, 4.4, 2.2, 6.4],
)
body("另有两项需要在文档中如实说明：需求 1.4.3 中的“多用户协同过滤”未实现，系统按单用户本地库设计；评分项中的“多智能体协同”与“本地模型部署加分”未单独实现，后者可通过在配置中把接口指向本机 Ollama 完成，代码已支持，但未作为演示主路径。")

# ---------------- 3 架构 ----------------
h("3  系统架构与数据流", 1)
body("系统采用“薄前端 + 单进程后端 + 单文件数据库”的结构。前端只有三个文件（页面、逻辑、样式），不引入构建工具；后端按职责拆成八个模块，互相之间只通过数据库和函数调用衔接，便于单机部署与排错。")
caption("表 2  后端模块职责", above=True)
table(
    ["模块", "职责"],
    [
        ["app/config.py", "读取 .env 配置；判断大模型是否真正可用（识别占位 key）"],
        ["app/db.py", "SQLite 建表与查询封装；论文、文本块、参考文献、翻译、推荐五张表"],
        ["app/parser.py", "PDF 结构解析：首页信息、章节层级、正文块、表格、参考文献、OCR"],
        ["app/pipeline.py", "入库流程编排、暂存与确认、重复判定、版本差异、删除保护"],
        ["app/search.py", "中英术语扩展、混合检索、按篇配额、参考文献降权"],
        ["app/llm.py", "模型调用封装：检索式生成、重排、问答、翻译、综述、大纲、架构图"],
        ["app/graph.py", "引用网络构建、PageRank、角色判定、综述素材聚合"],
        ["app/arxiv.py", "arXiv 检索、推荐打分、按编号下载入库"],
    ],
    widths=[3.6, 12.4],
)
body("数据流可以概括为五步：上传的 PDF 先落盘，再由解析器抽出带页码与章节的结构化文本块；判重模块用标题、摘要、首作者三个信号判断是否与库内重复；确认后写入 SQLite；提问时检索模块先做术语扩展与多路召回，再交给模型重排与作答；图谱模块则只读参考文献表，把“库内论文引用库内论文”的关系连成有向图。整条链路中，模型只负责语言组织与排序，事实与出处始终来自解析结果。")

# ---------------- 4 功能 ----------------
h("4  六个功能页签", 1)
h("4.1  文库：批量入库与判重", 2)
body("支持拖拽或选择多个 PDF 一次上传，也可直接粘贴 arXiv 编号下载。上传后进入暂存区，系统给出解析摘要（页数、章节数、文本块数、参考文献条数）与重复判定结果；判定为重复时并列展示库内版本与本次版本的标题、摘要、作者差异，由使用者决定跳过、并存还是替换。删除论文时会检查同一 PDF 是否被其他记录共用，避免误删文件。")
h("4.2  阅读：原文、翻译与引用跳转", 2)
body("阅读页左侧按页渲染 PDF 原始版面，右侧按章节列出解析后的文本块。点击任意段落可逐段翻译，也可开启中英对照，两栏按滚动比例联动；鼠标悬停在已翻译段落上会浮出译文。正文中的 [n] 上标可点击跳到对应参考文献条目，参考文献标题旁提供“返回正文”按钮回到原位置。整篇论文可一键导出为 Markdown 或 HTML，保留章节顺序与参考文献。")
h("4.3  问答：带出处的检索增强回答", 2)
body("提问框下方可勾选参与检索的论文，不勾选则检索全库。系统先做中英术语映射与查询扩展，再由模型把中文问题压成英文检索式，多路召回后按篇配额合并，最后由模型在候选片段内重排并作答；答案下方列出引用片段、页码与章节。模型不可用时自动切换为原文证据模式，直接展示命中的原文。")
h("4.4  图谱：引用网络与核心论文", 2)
body("图谱以论文为节点、以“参考文献中引用了库内另一篇”为有向边。全库视图可直接看出领域骨架；只勾选一篇时，系统自动补上它的直接引用邻居，避免出现只有一个孤点的图。右侧列出基石论文（被引最多且被引大于零）、边缘论文（只引出不被引）与被引最多的外部工作。基于同一份引用上下文，还可以生成领域综述与未来工作建议。")
image(IMG_GRAPH, 15.2)
caption("图 1  全库引用网络（27 篇论文、92 条引用边，基石为 BERT）")
h("4.5  写作：框架、架构图与实验图表", 2)
body("论文框架：输入一句研究想法，系统把勾选的论文作为参考文献清单交给模型，生成含摘要、引言、相关工作、方法、实验、结论的框架，参考文献只允许从清单中选取，避免编造文献。架构图：用箭头描述结构，Mermaid 直接在页面内渲染为框图，也可输出 TikZ 或 Graphviz 源码。实验数据可视化：上传 CSV 或 XLSX，第一列为横轴、其余列为数值，生成折线、柱状或雷达图，并自动配中英文图注与统计摘要。")
image(IMG_PLOT, 15.2)
caption("图 2  实验数据可视化：示例数据生成的 BLEU 对比柱状图")
h("4.6  推荐与反馈", 2)
body("按文库主题抓取 arXiv 最新论文，按摘要重合度排序，摘要中提到开源代码的加权优先，并给出推荐理由。每条推荐可“下载入库”或标记“有用/不相关”，反馈写回数据库，用于后续排序。后台线程每 6 小时自动刷新一次，无需手动触发。")

# ---------------- 5 关键技术 ----------------
h("5  关键技术实现", 1)
h("5.1  结构感知的 PDF 解析", 2)
body("通用 PDF 文本提取会把“1”与“Introduction”拆成两段、把正文句子误判成标题、把参考文献之后的附录整段丢掉。解析器改为按编号深度定层级：编号块与紧随其后的标题块先合并，再按“1 → 一级、1.1 → 二级”的规则赋层级；标题候选需通过长度、数字占比、是否含 URL/邮箱/页码戳等过滤。首页信息单独处理，按行聚类后重排，解决双栏论文作者与单位错位。参考文献之后的附录若出现字号明显大于正文的短行，即判定为附录起点，截断参考文献区，其后内容仍按正文入库——这一处修复让 BERT 的入库文本块从 153 增至 328。表格单独成块并在检索时豁免“数字占比过高降权”，避免实验数据表检不到。")
h("5.2  三信号论文判重", 2)
body("同一篇论文的 v1 与 v7 版本，首页多了一行授权声明、换行方式也不同，单靠文本指纹相似度只有 0.75，会漏判。系统改为三个信号联合判断：标题相似度、摘要前 320 字相似度、首作者前两词是否命中，满足“标题高相似且摘要相似”或“标题极高相似且作者命中”或“文本指纹极高”任一条件即判为重复，并把差异项列给使用者。实测同一篇论文两个版本判定为重复、相似度 0.954，建议保留库内版本。")
h("5.3  自实现 PageRank 与角色判定", 2)
body("引用图谱最初直接调用网络分析库的 PageRank，在本机因缺少科学计算依赖导致接口报错。改为用矩阵幂迭代自行实现：悬挂节点概率均分、阻尼系数 0.85、迭代 60 次，结果与标准实现一致且不再依赖额外包。角色判定不采用“排名第一即基石”的做法，而是要求入度大于零且等于全图最大，避免出现“被引 0 却被标成基石”的错误结论；只引出不被引的节点判为边缘。")
h("5.4  跨语言检索的四层处理", 2)
body("中文提问、英文论文，词面匹配几乎无效。系统做了四层处理：内置约 45 组中英术语映射并对问题做查询扩展；由模型把中文问题压成英文检索式；候选片段按语义重排取前 8 条；多路召回按篇配额合并，保证长论文不被短论文挤占。参考文献条目单独建块并以较低权重参与检索，避免答非所问时被引文带偏。")
h("5.5  扫描件离线 OCR", 2)
body("扫描版 PDF 没有文字层，直接解析结果是空页。系统在逐页解析时检测文本量，低于 40 字符即调用本地 OCR 引擎按 200 dpi 识别，并把识别框坐标换算回 PDF 页面坐标，使识别结果仍能定位到原文位置。OCR 引擎完全离线，不依赖云服务。")
h("5.6  引用双向跳转与中英对照联动", 2)
body("正文中的引用编号被渲染为可点击上标，点击后跳到参考文献区并高亮对应条目，同时记录返回位置；参考文献区提供“返回正文”按钮，回到原来的页码与滚动位置。中英对照采用左右两栏按滚动比例互相镜像，并用标志位防止来回触发；当前页尚无译文时自动补译。")

# ---------------- 6 实测 ----------------
h("6  实测数据", 1)
body("以下数据均在本机（Windows 11、i7-12800HX、RTX 4070 Laptop、16 GB 内存）实测取得，测试脚本随源码一同提交。")
caption("表 3  关键实测数据", above=True)
table(
    ["测试项", "结果"],
    [
        ["单篇解析（Attention v7）", "15 页、24 个章节、461 个文本块、40 条参考文献"],
        ["单篇解析（BERT）", "16 页、25 个章节、388 个文本块、59 条参考文献"],
        ["批量入库", "24 个 PDF：22 篇成功、2 篇判重跳过、0 失败，单篇 12–115 秒"],
        ["扫描件 OCR", "4 页扫描版 PDF 用时 38.2 秒，标题、年份、摘要、章节均识别正确"],
        ["长文档", "540 页、68 MB 合成文档用时 306 秒（0.57 秒/页），18201 个文本块"],
        ["引用图谱（全库）", "27 个节点、92 条引用边；基石 BERT 被引 13 次"],
        ["引用图谱（单篇）", "只勾 Attention 时自动补邻居，10 个节点、23 条边"],
        ["问答样例题", "9 题中 7 题可用；第 4、7 题存在召回缺口，第 9 题材料本身无答案"],
        ["整篇导出", "Attention 导出 Markdown 42 KB、HTML 49 KB"],
        ["参考文献价值筛查", "Attention 40 条中 17 条仅被正文引用 1 次、9 条未被引用"],
    ],
    widths=[5.0, 11.0],
)
body("三处未达标的样例题需要说明：第 4 题要求从表格中取“被超越模型的 BLEU 值”，目标行在表格块中未被召回；第 7 题要求 GPT-1 的参数量，答案所在段落未被召回；第 9 题问 GPT 系列的三代上下文长度，原文没有明确给出对应数值，系统回答“材料未提及”，属诚实结论而非缺陷。前两题的根因是纯词面检索对数值型问题的召回偏弱，后续计划引入本地嵌入模型做向量召回。")

# ---------------- 7 创新点 ----------------
h("7  创新点", 1)
h("7.1  技术层面", 2)
body("第一，解析器围绕论文排版规律设计规则，而不是套用通用文本提取：编号定层级、作者行聚类、附录截断、表格独立成块，四处改动都由真实错误驱动，并有对应的回归验证。")
body("第二，判重从单阈值改为三信号联合，并对“同篇不同版本”这一真实场景做了实测校准，判定结果同时给出差异项，把决定权交回使用者。")
body("第三，引用图谱不依赖额外科学计算包，自实现 PageRank，并把“基石”定义收紧为“必须被引”，保证结论可解释。")
body("第四，检索链路把术语映射、模型检索式、语义重排、按篇配额串成四层，专门解决中文提问英文论文的错配问题。")
h("7.2  应用层面", 2)
body("第一，原文证据是默认态而非兜底：模型不可用时系统仍能返回带页码的原文片段，演示与答辩不会因网络或额度中断。")
body("第二，一次解析、多次复用：同一份解析结果同时支撑阅读、问答、图谱、综述、写作五类功能，避免重复调用模型。")
body("第三，把“引用是否真被用到”变成可筛查的指标：按正文引用次数给参考文献分级，提示哪些是为凑数而列。")
body("第四，模型可插拔且可本地化：换模型只改配置，指向本机 Ollama 即可完全离线运行。")

# ---------------- 8 部署 ----------------
h("8  部署与使用", 1)
body("环境要求：Windows 10/11，Python 3.10 及以上。首次部署在项目根目录执行依赖安装，随后双击“启动.cmd”，浏览器打开 127.0.0.1:8000 即可使用。模型配置写在 .env：填入 OpenAI 兼容的接口地址、模型名与密钥；未填写时系统以原文证据模式运行。")
body("目录结构：app 为后端源码，static 为前端页面，data 存放 PDF、解析结果、数据库与导出图，docs 存放技术文档、需求对照与作品介绍，tests 为可复跑的自测脚本。所有数据均落在项目目录内，不写系统盘其他位置，卸载时直接删除目录即可。")
body("自测脚本包括：端到端十步流程、前端按钮真实点击、阅读页引用跳转与对照联动、扫描件 OCR、540 页长文档压测、图谱与写作接口验收。每个脚本都会打印关键数值，便于复现本文第 6 节的数据。")

# ---------------- 9 限制 ----------------
h("9  已知限制与后续计划", 1)
body("一是数值型问题的召回仍偏弱：纯词面检索对“某个数字在第几页的表格里”这类问题不够稳，计划引入本地嵌入模型补向量召回。二是系统按单用户本地库设计，未实现多用户与协同过滤。三是本地部署无鉴权，直接开放公网存在被删库的风险，因此未提供在线演示地址。四是 PDF 表格抽取采用文本块近似，复杂跨页表格的结构还原有限，目前已通过“表格独立成块 + 检索豁免”保证可检索，但不保证结构完整。五是 OCR 逐页识别较慢，扫描件页数多时解析时间会明显上升。")
body("后续优先做三件事：补向量召回以提升数值题命中；给接口加最小鉴权后再考虑公网演示；把引用图谱扩展到“库外文献”节点，使领域脉络不因库内论文数量受限。")

# ---------------- 附录 ----------------
h("附录 A  主要接口清单", 1)
table(
    ["接口", "用途"],
    [
        ["GET /api/status", "服务状态、模型是否可用、库内统计"],
        ["GET /api/papers", "论文列表"],
        ["POST /api/upload", "批量上传并给出判重结果"],
        ["POST /api/upload/confirm", "确认入库（跳过/并存/替换）"],
        ["POST /api/ingest/arxiv", "按 arXiv 编号下载入库"],
        ["GET /api/papers/{id}/struct", "论文结构：章节、文本块、参考文献"],
        ["GET /api/papers/{id}/export", "导出 Markdown 或 HTML"],
        ["POST /api/ask", "检索增强问答，返回答案与引用"],
        ["POST /api/translate/range", "按页范围翻译，用于中英对照"],
        ["POST /api/graph", "引用图谱：节点、边、基石、边缘、外部引用"],
        ["POST /api/survey", "基于引用上下文生成领域综述"],
        ["POST /api/futurework", "生成未来工作建议"],
        ["POST /api/write/outline", "生成论文框架与参考文献"],
        ["POST /api/write/diagram", "生成 Mermaid / TikZ / Graphviz 架构图"],
        ["POST /api/plot", "CSV/XLSX 生成折线、柱状、雷达图"],
        ["POST /api/recommend", "arXiv 新论文推荐"],
        ["POST /api/refs/batch", "参考文献价值筛查"],
    ],
    widths=[6.2, 9.8],
)

OUT.parent.mkdir(parents=True, exist_ok=True)
doc.save(str(OUT))
print("saved:", OUT, OUT.stat().st_size)
