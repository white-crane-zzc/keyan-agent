# -*- coding: utf-8 -*-
"""生成《科研小助手 Agent 技术文档》（PDF）。"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph,
                               Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = Path(r"E:\项目\科研小助手")
OUT = ROOT / "docs" / "科研小助手Agent-技术文档.pdf"
PAGE_HINT = 30

FONTS = Path(r"C:\Windows\Fonts")
pdfmetrics.registerFont(TTFont("SimSun", str(FONTS / "simsun.ttc"), subfontIndex=0))
pdfmetrics.registerFont(TTFont("SimHei", str(FONTS / "simhei.ttf")))
pdfmetrics.registerFont(TTFont("Times", str(FONTS / "times.ttf")))
pdfmetrics.registerFont(TTFont("TimesBd", str(FONTS / "timesbd.ttf")))
registerFontFamily("SimSun", normal="SimSun", bold="SimHei", italic="SimSun", boldItalic="SimHei")

INK = colors.HexColor("#1a1a1a")
GREY = colors.HexColor("#555555")
LINE = colors.HexColor("#b0b0b0")
HEADBG = colors.HexColor("#E9E9E9")

W = 10.5
S = {
    "ct": ParagraphStyle("ct", fontName="SimHei", fontSize=25, leading=34, alignment=TA_CENTER,
                         textColor=INK, spaceAfter=8),
    "cs": ParagraphStyle("cs", fontName="SimSun", fontSize=12.5, leading=22, alignment=TA_CENTER,
                         textColor=GREY),
    "cm": ParagraphStyle("cm", fontName="SimSun", fontSize=10, leading=18, textColor=INK),
    "h1": ParagraphStyle("h1", fontName="SimHei", fontSize=15, leading=24, textColor=INK,
                         spaceBefore=12, spaceAfter=7, keepWithNext=1),
    "h2": ParagraphStyle("h2", fontName="SimHei", fontSize=11.5, leading=20, textColor=INK,
                         spaceBefore=9, spaceAfter=4, keepWithNext=1),
    "body": ParagraphStyle("body", fontName="SimSun", fontSize=W, leading=17, firstLineIndent=W * 2,
                           alignment=TA_JUSTIFY, textColor=INK, wordWrap="CJK", spaceAfter=3),
    "item": ParagraphStyle("item", fontName="SimSun", fontSize=W, leading=17, leftIndent=W * 2,
                           alignment=TA_JUSTIFY, textColor=INK, wordWrap="CJK", spaceAfter=3),
    "cap": ParagraphStyle("cap", fontName="SimSun", fontSize=8.5, leading=13, alignment=TA_CENTER,
                          textColor=GREY, spaceBefore=3, spaceAfter=8),
    "tcap": ParagraphStyle("tcap", fontName="SimSun", fontSize=8.5, leading=13, alignment=TA_CENTER,
                           textColor=GREY, spaceBefore=5, spaceAfter=3),
    "th": ParagraphStyle("th", fontName="SimHei", fontSize=8, leading=11.5, alignment=TA_CENTER,
                         textColor=INK, wordWrap="CJK"),
    "td": ParagraphStyle("td", fontName="SimSun", fontSize=8, leading=11.5, alignment=TA_LEFT,
                         textColor=INK, wordWrap="CJK"),
    "tdc": ParagraphStyle("tdc", fontName="SimSun", fontSize=8, leading=11.5, alignment=TA_CENTER,
                          textColor=INK, wordWrap="CJK"),
    "h1n": ParagraphStyle("h1n", fontName="SimHei", fontSize=15, leading=24, textColor=INK,
                          spaceBefore=0, spaceAfter=7, keepWithNext=1),
    "toc1": ParagraphStyle("toc1", fontName="SimHei", fontSize=10.5, leading=23, textColor=INK),
}
DOCTITLE = "科研小助手 Agent　技术文档"


def P(t, s="body"):
    return Paragraph(t, S[s])


def H1(t):
    return Paragraph(t, S["h1"])


def H2(t):
    return Paragraph(t, S["h2"])


def table(rows, widths, cap=None, align=None):
    data = []
    start = 0
    if cap:
        data.append([Paragraph(cap, S["tcap"])] + [""] * (len(rows[0]) - 1))
        start = 1
    for i, row in enumerate(rows):
        data.append([Paragraph(c, S["th" if i == 0 else ((align or [])[j] if align else "td")])
                     for j, c in enumerate(row)])
    t = Table(data, colWidths=widths, repeatRows=start + 1, hAlign="CENTER")
    style = [
        ("GRID", (0, start), (-1, -1), 0.5, LINE),
        ("BACKGROUND", (0, start), (-1, start), HEADBG),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    if cap:
        style += [("SPAN", (0, 0), (-1, 0)),
                  ("TOPPADDING", (0, 0), (-1, 0), 6),
                  ("BOTTOMPADDING", (0, 0), (-1, 0), 3),
                  ("LEFTPADDING", (0, 0), (-1, 0), 0),
                  ("RIGHTPADDING", (0, 0), (-1, 0), 0)]
    t.setStyle(TableStyle(style))
    return t


class Doc(BaseDocTemplate):
    def __init__(self, path):
        BaseDocTemplate.__init__(self, path, pagesize=A4, leftMargin=2.2 * cm,
                                 rightMargin=2.2 * cm, topMargin=2.3 * cm, bottomMargin=2.1 * cm,
                                 title="科研小助手 Agent 技术文档", author="科研小助手 Agent")
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="n")
        self.addPageTemplates(PageTemplate("n", [frame], onPage=self._deco))

    def _deco(self, canvas, doc):
        canvas.saveState()
        if doc.page > 1:
            canvas.setStrokeColor(LINE)
            canvas.setLineWidth(0.4)
            canvas.line(2.2 * cm, A4[1] - 1.65 * cm, A4[0] - 2.2 * cm, A4[1] - 1.65 * cm)
            canvas.setFont("SimSun", 8)
            canvas.setFillColor(GREY)
            canvas.drawString(2.2 * cm, A4[1] - 1.5 * cm, DOCTITLE)
            canvas.setFont("SimSun", 9)
            canvas.setFillColor(INK)
            canvas.drawCentredString(A4[0] / 2, 1.35 * cm, "第 %d 页" % doc.page)
        canvas.restoreState()

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name in ("h1", "h2"):
            level = 0 if flowable.style.name == "h1" else 1
            text = flowable.getPlainText()
            key = "k%d-%s" % (level, text)
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=level, closed=False)
            if level == 0:
                self.notify("TOCEntry", (level, text, self.page, key))


def build(out_path=OUT):
    doc = Doc(str(out_path))
    story = []

    # 封面
    story += [Spacer(1, 4.6 * cm),
              P("科研小助手 Agent", "ct"),
              P("面向科研论文全流程的解析、问答、图谱与写作辅助系统", "cs"),
              Spacer(1, 0.8 * cm),
              P("技术文档", "ct"),
              Spacer(1, 1.4 * cm)]
    meta = Table([[Paragraph(a, S["cm"]), Paragraph(b, S["cm"])] for a, b in [
        ("参赛赛事", "全国计算机应用能力与数字素养大赛暨第九届传智杯 AI 大模型创新应用挑战赛（省赛）"),
        ("作品形态", "本地部署的 Web 应用（FastAPI + SQLite + 原生前端）"),
        ("模型接入", "OpenAI 兼容接口，可插拔（默认 DeepSeek，可指向本机 Ollama）"),
        ("文档内容", "系统设计、AI 技术方案、功能实现、测试与部署"),
        ("文档篇幅", "共 %d 页，正文 8 章加附录" % PAGE_HINT),
        ("提交日期", "2026 年 11 月"),
    ]], colWidths=[2.8 * cm, 12.6 * cm], hAlign="CENTER")
    meta.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#dcdcdc")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
    ]))
    story += [meta, PageBreak()]

    # 前言
    story += [Paragraph("前　　言", S["h1n"]),
              P("本文件说明科研小助手 Agent 的设计与实现：为什么这样选技术路线、系统内部如何组织、AI 能力具体落在哪些环节、实测到什么程度、还有哪些边界没有解决。"
                "行文顺序即读者的理解顺序——先交代作品定位与要解决的问题，再给出需求边界与系统结构，随后展开 AI 技术方案与核心功能实现，最后是测试、部署与创新点。"),
              P("全文以可核对的实测数据说话：库规模、图谱规模、样例题命中情况、干净环境复现结论均给出测量方法；未通过验证的功能不写入正文，未达标的项目单列并说明原因。"
                "文中的数字与运行截图取自同一台机器、同一轮使用，可相互印证。"),
              P("作品的功能演示、界面截图与提交材料清单见另份《作品介绍文档》，本文件只讨论技术本身。")]

    # 目录
    story += [Spacer(1, 0.75 * cm), Paragraph("目　　录", S["h1n"])]
    toc = TableOfContents()
    toc.levelStyles = [S["toc1"]]
    story += [Spacer(1, 0.15 * cm), toc, PageBreak()]

    # 一
    story += [H1("一、项目概述"),
              H2("（一）定位与目标"),
              P("科研小助手 Agent 是一个本地运行的科研论文辅助系统。它把“把论文存进来—读懂它—问它问题—看清论文之间的关系—照着它写初稿—追踪新论文”这几件事串成一条完整流水线，"
                "而不是把若干互不相干的 AI 功能拼在一个页面上。系统以一篇 PDF 为起点，自动完成结构解析、去重入库、检索增强问答、引用网络构建与写作素材生成，全部结果在同一个界面内连续使用。"),
              P("选题出发点是科研新手真实卡住的地方往往不是“不会用大模型”，而是三件事：论文太多、英文太长，逐篇精读的时间成本极高；通用聊天模型回答论文问题时给不出可核对的原文位置，"
                "无法直接用于写作；“这几篇之间谁引了谁、哪篇是绕不开的基石”这类关系问题，靠人脑记不住，靠聊天模型又容易编。系统用“原文证据 + 结构化数据”两个抓手应对："
                "所有回答都带页码与章节引用，所有引用关系都来自解析出的参考文献条目，而不是模型记忆。"),
              P("设计目标确定为四条：解析要细到章节与表格、回答要能回到原文、关系要来自文献而非模型、部署要在一台普通笔记本电脑上完成且断网可用。当前演示库共 27 篇论文、"
                "22214 个文本块、2369 条参考文献条目，引用图谱含 27 个节点、92 条有向边，覆盖 Attention、BERT、GPT 系列及其后的主流大模型技术路线。"),
              H2("（二）作品形态与运行条件"),
              P("形态为本地部署的单进程 Web 应用：后端 FastAPI，数据库为单文件 SQLite，前端为三个原生文件，不依赖 Node 或任何构建工具。运行条件为 Windows 10/11 加 Python 3.10 以上，"
                "首次安装依赖需联网，装好后可断网运行；接入大模型需自行配置密钥，未配置时系统以原文证据模式工作。")]

    # 二
    story += [H1("二、需求分析"),
              P("需求按功能域分为六类：入库与解析、问答、阅读与翻译、论文获取与推荐、库内分析与生成、写作辅助。分析时把每条需求拆成“输入—处理—可核对的输出”三步，先确认输出能不能被验证，再决定技术路线；"
                "凡是输出无法回原文核对的功能，一律不作为主路径，只作辅助。逐项落地情况见表 1，“部分完成”的边界在第六章如实列出。"),
              table([
                  ["需求条目", "核心考察点", "实现情况", "验证证据"],
                  ["内容去重", "同篇不同版本判重，提示保留哪一版", "完成：三信号联合判定，并列差异", "论文 v1/v7 实测判重，相似度 0.954"],
                  ["文件解析", "标题、作者、摘要、各级标题、表格、图表、公式、参考文献、附录", "完成（图表按文本块近似，公式保留原文不解析语义）", "27 篇入库，BERT 文本块由 153 增至 328"],
                  ["单篇问答", "给出参考原文，暴露模型幻觉", "完成：答案必带引用片段与页码", "样例题逐题比对"],
                  ["多篇问答", "跨论文对比", "完成：多路召回按篇配额合并", "多篇对比样例题命中"],
                  ["阅读排版", "双栏、公式、表格排版", "完成：按页渲染原始版面", "阅读页截图"],
                  ["树状导航与跳转", "标题树定位、引用双向跳转", "完成", "界面实测跳转与返回"],
                  ["翻译", "部分/整篇翻译、中英对照、代码公式不译", "完成：逐段与整篇，整篇导出 Markdown/HTML", "翻译接口与对照联动实测"],
                  ["按标题或引用自动下载", "按标题搜索下载、按参考文献批量下载", "部分完成：接口支持按 arXiv 编号或关键词检索下载；批量下载接口已实现（按正文引用次数筛出候选并下载命中 arXiv 编号的条目），阅读页只接了「引用价值筛查」，未接一键下载按钮", "接口返回与阅读页筛查实测"],
                  ["新论文推荐", "按相关性推荐、给理由、含代码优先、可反馈", "完成（协同过滤未实现）", "推荐接口与反馈写库实测"],
                  ["库内分析与生成", "图谱、基石论文、自动综述、未来工作", "完成", "图谱 27 节点 92 边，基石 BERT"],
                  ["框架生成", "摘要至参考文献，文献不编造", "完成：文献只取自勾选清单", "写作页实测"],
                  ["架构图生成", "TikZ、Graphviz、Mermaid 脚本", "完成：页面内渲染，另可导出源码", "界面出图"],
                  ["数据可视化", "表格、折线、柱状、雷达图与图注", "完成：上传 CSV/XLSX 生成图表与中英文图注", "示例数据出图"],
                  ["摘要英译", "中文摘要转英文", "完成", "写作页实测"],
              ], [3.1 * cm, 4.7 * cm, 4.6 * cm, 3.2 * cm], "表 1　需求条目与实现情况",
                  align=["tdc", "td", "td", "td"])]

    # 三
    story += [H1("三、系统架构设计"),
              H2("（一）分层结构"),
              P("系统采用“薄前端 + 单进程后端 + 单文件数据库”的四层结构。表现层为不依赖框架与构建工具的原生页面，三个文件分别为页面、样式与逻辑；接口层由 FastAPI 提供 HTTP 接口；"
                "业务层拆成八个职责模块，模块之间只通过函数调用与数据库衔接；数据层为 SQLite 单文件加 PDF 原文与导出图；模型层通过 OpenAI 兼容接口接入，可在配置中切换厂商或指向本机服务。"),
              table([
                  ["模块", "职责", "关键实现"],
                  ["config.py", "读取配置与环境变量", "接口地址、模型名、检索参数集中管理"],
                  ["db.py", "数据库连接与读写", "论文、文本块、参考文献、反馈四类表"],
                  ["parser.py", "PDF 解析与结构化", "编号定层级、首页行聚类、附录截断、表格独立成块、扫描件 OCR"],
                  ["pipeline.py", "入库流水线与判重", "标题/摘要/作者三信号判重，暂存区与差异展示"],
                  ["search.py", "检索与召回合并", "术语扩展、多路召回、按篇配额、引用块降权"],
                  ["graph.py", "引用图谱与角色判定", "自实现 PageRank，基石/边缘/外部高被引判定"],
                  ["llm.py", "模型调用与降级", "统一客户端、超时重试、失败切原文证据模式"],
                  ["arxiv.py", "新论文抓取与推荐", "按文库主题抓取、摘要重合度排序、反馈写回"],
                  ["main.py", "接口编排", "六个页签所需的全部接口与静态资源托管"],
              ], [2.4 * cm, 4.6 * cm, 8.6 * cm], "表 2　后端模块职责",
                  align=["tdc", "td", "td"]),
              H2("（二）数据流"),
              P("数据流可概括为五步：上传的 PDF 先落盘，先按整份文件 sha256 做一层精确判重——同一条文件再传一次时直接弹选择，不再重复解析；确认是新内容后，解析器抽出带页码与章节的结构化文本块，"
                "判重模块再用标题、摘要、首作者三个信号判断是否与库内的另一版本重复；确认后写入数据库；"
                "提问时检索模块先做术语扩展与多路召回，再交给模型在候选片段内重排作答；图谱模块只读参考文献表，把“库内论文引用库内论文”的关系连成有向图。整条链路中，模型只负责语言组织与排序，"
                "事实与出处始终来自解析结果。"),
              H2("（三）数据与存储设计"),
              P("数据库共四类表：论文表记录标题、作者、年份、摘要、页数与文件路径；文本块表记录所属论文、页码、章节标题、层级与文本内容，是检索与问答的基本单位；"
                "参考文献表记录原文条目、解析出的作者年份标题与是否命中库内论文，图谱与引用跳转均基于此；反馈表记录推荐项的“有用/不相关”标记，用于后续排序。"
                "所有数据与文件都落在项目目录内，不写系统盘其他位置，整目录复制即迁移，删除目录即完成卸载。")]

    # 四
    story += [H1("四、AI 技术方案"),
              P("本章说明 AI 部分的技术路线：为什么这样选、怎么接进系统、做了哪些优化，实现细节见第五章。"),
              H2("（一）技术选型理由"),
              P("第一，用检索增强生成（RAG）而不是微调。论文库随使用者不断变化，微调无法覆盖新入库的论文；论文问答的答案必须能指向原文位置，微调模型的输出无法溯源；"
                "本地笔记本也不具备训练与推理微调模型的算力。RAG 把“事实”交给解析与检索，把“表达”交给模型，两条职责清晰、各自可验证。"),
              P("第二，用 OpenAI 兼容接口而不是绑定单一厂商 SDK。同一套代码可通过修改配置切换到 DeepSeek、豆包、Kimi、通义，也可指向本机 Ollama 实现全离线运行；"
                "接口形态统一后，超时、重试、降级逻辑只需实现一次。默认接入 DeepSeek，理由是中文理解与学术英文阅读质量稳定、按量计费成本低、国内直连无需额外网络条件。"),
              P("第三，首版检索采用“词面召回 + 模型重排”而不是本地向量库。向量检索需要额外的嵌入模型与依赖体积，会在普通笔记本上抬高首次安装成本；词面召回加术语映射已能覆盖大部分概念题，"
                "再由模型在候选片段内重排补足语义匹配。代价是数值型问题的召回偏弱，这一点在第六章如实列出，并列为引入向量召回的理由。"),
              P("第四，扫描件 OCR 选择完全离线的本地引擎，而不是云 OCR 接口：论文含未公开内容，上传云端不合适；离线引擎随依赖安装，断网可用，识别框坐标可换算回 PDF 坐标，保证结果仍能定位原文。"),
              H2("（二）集成方式"),
              P("模型接入由一个统一的客户端完成：配置从 .env 读取接口地址、模型名与密钥，请求统一走 OpenAI 兼容的对话接口；调用处统一封装超时、重试与错误分类，"
                "任何一类失败都不抛给前端，而是标记降级并按原文证据模式返回结果。"),
              P("提示词采用“结构化约束 + 片段封闭”的方式：检索先固定候选片段集合，模型只被允许在该集合内作答；回答必须按“结论 + 引用编号”的格式输出，引用编号与片段一一对应，"
                "前端据编号渲染页码与章节；写作框架的参考文献只允许从使用者勾选的清单中选取，模型无权新增文献。这一约束把“事实来源”和“语言组织”在提示层就分开，显著降低幻觉。"),
              P("模型在系统中的定位因此是“读得快的助手”，而不是“知道一切的专家”：它负责把中文问题压成检索式、在候选片段内排序与作答、把结构化提纲扩写成段落；"
                "数值、引用关系、统计结果一律由确定性代码计算。"),
              H2("（三）优化策略"),
              P("检索侧：文本块按 900 字符切分并做相似度 0.90 的去重，减少重复片段占用配额；问答默认取前 8 条候选（TOP_K=8），在召回质量与响应时延之间取平衡；"
                "参考文献块单独建块并降权；表格块豁免“数字占比过高”的降权规则，保证实验数据可检索。"),
              P("生成侧：先重排后作答，避免模型在长上下文中迷失；回答长度按片段数量自适应，片段少时直接列证据；写作页分“框架生成”与“章节扩写”两步调用，"
                "每一步的输入都限定在已知材料内，便于定位问题。"),
              P("成本与稳定性侧：解析结果一次入库多次复用，同一篇论文不重复解析、不重复调用模型；推荐任务放后台线程按 6 小时周期刷新，避免阻塞前端；"
                "所有模型调用都设有超时与失败降级，未配置密钥时系统直接进入证据模式，不产生无效请求。上传链路另做两处提速：表格识别从整份逐页扫描改为“题注页门控 + 四线程并行”，"
                "77 页论文解析由 78.7 秒降到 36.5 秒且输出一致；重复文件的判定提前到解析之前，同一条文件再传 0.2 秒内给出结论，解析与入库改到线程池执行，上传期间界面不再卡住。"),
              P("工程侧：依赖统一到 requirements.txt 单一来源，启动脚本按清单安装，避免多份手写清单不一致；交付包剔除演示视频、全部成品文档与可再生的缓存数据，"
                "既控制体积便于他人复现，也避免文档版本与源码版本不同步。"),
              H2("（四）关键技术实现"),
              P("结构感知解析：编号深度定层级、首页行聚类、附录截断、表格独立成块，四处规则均由真实错误驱动并有回归验证。判重两级：先整文件 sha256 精确判定“同一条文件”，再以标题、摘要、首作者三信号判定“同篇不同版本”，两级都输出差异项交使用者决定，替换时删除旧记录、并存时自动改名。"
                "跨语言检索：术语映射、模型检索式、语义重排、按篇配额四层串联。引用图谱：自实现 PageRank，基石定义收紧为必须被引；只选单篇时补全直接引用邻居。"
                "引用双向跳转与中英对照：正文引用渲染为可点击上标并记录返回位置，两栏按滚动比例镜像并用标志位防抖。扫描件 OCR：逐页检测文本量，低于 40 字符即按 200 dpi 识别并回填坐标。"
                "本地出图：服务端 matplotlib 出图并注册中文字体，图注由列名与统计量自动生成。")]

    # 五
    story += [H1("五、核心功能实现"),
              H2("（一）解析与入库"),
              P("解析器逐页读取文本块，先识别首页的作者与单位区，再按编号规则建立章节层级；参考文献区单独解析出条目，逐条尝试匹配库内论文；附录区按字号规则截断。"
                "扫描页在文本量不足时触发离线 OCR。入库流水线先按文件 sha256 判“完全同一条”，再按三信号判“同篇不同版本”，随后写库、生成检索索引，并在暂存区向使用者展示解析摘要与判重差异；"
                "选“保留新版”时删除库内旧记录、选“两个都保留”时新文件自动改名，两种处理都不会出现两条记录共用一个 PDF 文件。"),
              H2("（二）阅读与翻译"),
              P("阅读页左侧把 PDF 按页渲染为图片以保留原始版面（双栏、公式、表格均不改排），右侧按章节树展示解析文本。点击段落发起逐段翻译，译文按段落缓存；"
                "中英对照时两栏按滚动比例互相镜像，当前页无译文时自动补译。整篇导出为 Markdown 或 HTML，保留章节顺序、段落结构与参考文献。"),
              H2("（三）检索增强问答"),
              P("提问后先做术语扩展与多路召回，候选片段按篇配额合并，再由模型在候选范围内重排并作答；返回值包含答案正文、引用片段列表（含页码与章节）与降级标记。"
                "未配置模型或调用失败时，答案直接返回命中片段的原文与出处，并标注“未配置大模型”。"),
              H2("（四）引用图谱与综述"),
              P("图谱以论文为节点、以文献条目命中库内论文为有向边，返回节点、边、角色判定与统计；基于同一份引用上下文可生成领域综述与未来工作建议。"
                "角色判定分基石、边缘、外部高被引三类，判定条件写在接口返回中，便于核对。"),
              H2("（五）写作辅助"),
              P("框架生成把勾选论文作为唯一文献来源，输出含摘要、引言、相关工作、方法、实验、结论的框架；架构图由前端解析 Mermaid 语法渲染，并可导出 TikZ 与 Graphviz 源码；"
                "数据可视化接收 CSV/XLSX，第一列为横轴、其余列为数值，按数据形态给出折线、柱状或雷达图，并自动生成中英文图注与统计摘要。"),
              H2("（六）推荐与反馈"),
              P("后台按文库主题抓取 arXiv 最新论文，按摘要重合度排序，摘要中提到开源代码的加权优先，并为每条推荐生成理由；使用者可下载入库或标记有用/不相关，"
                "反馈写回数据库用于后续排序。刷新周期 6 小时，可在配置中调整。")]

    # 六
    story += [H1("六、测试与部署"),
              H2("（一）测试方法与覆盖"),
              P("测试分三层推进。接口级：以脚本逐个调用状态、文库、图谱、问答、推荐、翻译、导出等接口，记录返回码与关键字段。界面级：用无头浏览器真实点击六个页签的按钮，验证交互路径而非只看接口。"
                "干净环境级：把交付压缩包解压到临时目录，新建干净虚拟环境、按 requirements.txt 安装依赖、启动服务再打接口，以此确认“换一台电脑能否跑起来”，而不是只在本机开发环境中验证。"
                "需要说明的是，这一轮复现是在本机新建的干净环境里完成的，没有再找第二台物理机器重复一遍；结论因此只能说明依赖清单与启动脚本不依赖开发机的残留状态，跨机差异（系统区域设置、显卡驱动、Python 版本细节）仍可能带来个别问题。"),
              P("随源码提交的自测脚本包括：端到端十步流程、前端按钮真实点击、阅读页引用跳转与对照联动、扫描件 OCR、540 页长文档压测、图谱与写作接口验收，以及干净环境复现。"
                "每个脚本都打印关键数值，便于复现本章数据；脚本未通过即视为功能未完成，不写入文档。"),
              H2("（二）实测数据"),
              table([
                  ["测试项", "方法", "结果"],
                  ["库规模", "GET /api/status", "27 篇论文、22214 个文本块、2369 条参考文献条目"],
                  ["引用图谱", "POST /api/graph 全库", "27 个节点、92 条有向边，基石识别为 BERT"],
                  ["接口可用性", "逐接口打点", "状态、文库、图谱、问答、推荐、翻译、导出均返回 200；未配置模型时问答与翻译按设计降级"],
                  ["问答准确性", "9 道样例题比对", "6 道命中并给出正确页码，3 道未达标（见下文）"],
                  ["扫描件 OCR", "4 页扫描版 PDF", "离线识别与坐标回填成功，耗时 38.2 秒"],
                  ["长文档压力", "540 页合成长文档", "解析与入库完成，未出现内存或超时中断"],
                  ["干净环境复现", "本机新解压 + 全新虚拟环境", "依赖安装成功、服务启动、库数据完整、六页签可用；未在第二台物理机器上复测"],
              ], [2.5 * cm, 4.6 * cm, 9.1 * cm], "表 3　关键实测数据",
                  align=["tdc", "td", "td"]),
              H2("（三）测试中发现并修复的真实缺陷"),
              P("图谱写回阶段曾出现“只有一个节点、被引为 0”的结果，原因是角色判定直接取排名首位而未要求入度大于零，改为“入度大于零且等于最大值”后恢复正常。写作页架构图曾把 Mermaid 源码当纯文本显示，"
                "改为前端解析渲染后正常出图。写作页数据可视化曾为空白，定位为绘图字体与后端出图链路问题，修复后可生成带中英文图注的图表。干净环境复现时发现依赖清单漏装离线 OCR 引擎，"
                "扫描件在别人的环境中会不可用，已统一依赖来源并重新打包验证。"),
              H2("（四）未达标项与原因"),
              P("9 道样例题中 3 道未达标：第 4 题要求从表格取“被超越模型的 BLEU 值”，目标行在表格块中未被召回；第 7 题要求 GPT-1 参数量，答案所在段落未被召回；"
                "第 9 题问 GPT 系列三代上下文长度，原文未明确给出对应数值，系统回答“材料未提及”，属诚实结论而非缺陷。前两题根因是纯词面检索对数值型问题召回偏弱，后续引入本地嵌入模型补向量召回。"),
              H2("（五）部署形态与可移植性"),
              P("部署形态为单机单进程：前端静态文件由后端一并托管，数据库为单文件，导出图写在项目目录内，不占用系统目录。交付包剔除演示视频与全部成品文档，只保留源码、库数据与论文原件，"
                "解压后为 72 个文件、78.3 MB，库内 27 篇论文与全部解析数据完整。干净环境复现结论为：在未安装过本项目依赖的干净虚拟环境中，按 requirements.txt 安装后服务可正常启动，"
                "库数据、六个页签与主要接口均可用；同一结论尚未在第二台物理机器上重复验证。需要说明的前提有三条：目标机需安装 Python 3.10 以上并联网完成首次依赖安装；包内不含密钥，大模型功能需自行配置；服务默认只监听本机地址，不对外开放。"),
              H2("（六）已知限制与后续计划"),
              P("一是数值型问题召回偏弱，纯词面检索对“某个数字在第几页的表格里”不够稳，计划引入本地嵌入模型补向量召回。二是系统按单用户本地库设计，未实现多用户与协同过滤。"
                "三是本地部署无鉴权，直接开放公网存在被删库风险，因此未提供在线演示地址。四是 PDF 表格抽取采用文本块近似，复杂跨页表格的结构还原有限，已通过“表格独立成块 + 检索豁免”保证可检索，"
                "但不保证结构完整。五是 OCR 逐页识别较慢，扫描件页数多时解析时间明显上升。"),
              P("后续优先做三件事：补向量召回提升数值题命中；给接口加最小鉴权后再考虑公网演示；把引用图谱扩展到库外文献节点，使领域脉络不受库内论文数量限制。")]

    # 七
    story += [H1("七、创新点说明"),
              H2("（一）技术创新点"),
              P("其一，解析规则由论文排版规律推导而非套用通用提取：编号定层级、首页行聚类、附录按字号截断、表格独立成块，四处改动都对应可复现的错误与回归验证。"
                "其二，判重做成分级：先按文件内容精确判“同一条”，再按三信号判“同篇不同版本”，并针对真实场景实测校准，输出差异项而非直接覆盖。"
                "其三，引用图谱自实现 PageRank，不引入科学计算依赖，同时把“基石”定义收紧为必须被引，使结论可解释、可核对。"
                "其四，检索链路的四层处理专门解决中文提问英文论文的错配，并用按篇配额避免长论文挤压短论文。"
                "其五，失败即降级的设计：模型不可用时不报错、不空转，而是切换到带页码的原文证据模式，保证系统在任何网络与额度状态下都可用。"),
              H2("（二）应用创新点"),
              P("其一，把“引用是否真被用到”变成可筛查指标：按正文引用次数给参考文献分级，提示哪些是为凑数而列，这是读论文的人真实关心但通用工具不给的结论。"
                "其二，一次解析、多次复用：同一份解析结果支撑阅读、问答、图谱、综述、写作五类功能，使用者的时间成本与部署者的调用成本同时下降。"
                "其三，图表与文档本地生成：架构图、数据图、导出文件都在本机产出，论文内容不出本机，适合未公开材料。"
                "其四，模型可插拔且可本地化：换模型只改配置，指向本机 Ollama 即可完全离线运行，便于在不同评测环境中复现。")]

    # 八
    story += [H1("八、总结与展望"),
              P("系统已完成立项设定的六类主体功能（去重入库、细粒度解析、检索问答、双栏阅读与翻译、引用图谱与写作、推荐与反馈），在一台普通笔记本上可完整跑通“入库—阅读—问答—图谱—写作—推荐”的闭环，主要接口与界面交互均经实测；"
                "未完成与未达标之处已在正文列出，不以设计预期代替实测结果。作品的核心判断是：把事实交给解析与检索、把表达交给模型，并让每一条结论都能回到原文核对，"
                "这比堆叠更多 AI 功能更能解决科研新手的真实问题。"),
              P("下一步的重点是三条：引入本地嵌入模型补向量召回，提升数值型与跨表述问题的命中；为接口增加最小鉴权与访问控制，使公网演示成为可能；把引用图谱扩展到库外文献节点，"
                "让领域脉络不再受库内论文数量限制。更长远的设想是把解析结果与个人笔记打通，使系统从“读论文的工具”变成“积累自己研究线索的工作台”。")]

    # 附录
    story += [H1("附录　接口与环境清单"),
              table([
                  ["方法", "路径", "作用"],
                  ["GET", "/api/status", "返回库规模、模型就绪状态与当前模型名"],
                  ["GET", "/api/papers", "返回论文清单（标题、作者、年份、文本块数）"],
                  ["POST", "/api/ask", "检索增强问答，返回答案、引用片段、页码与章节"],
                  ["POST", "/api/graph", "生成引用图谱，返回节点、边与角色判定"],
                  ["POST", "/api/recommend", "按文库主题生成 arXiv 推荐并给出理由"],
                  ["POST", "/api/translate", "逐段或整篇翻译，未配置模型时返回降级标记"],
                  ["GET", "/api/papers/{id}/export", "导出单篇为 Markdown 或 HTML"],
              ], [1.8 * cm, 5.4 * cm, 9.0 * cm], "表 4　主要接口",
                  align=["tdc", "td", "td"]),
              Spacer(1, 0.2 * cm),
              table([
                  ["类别", "依赖", "用途"],
                  ["运行环境", "Python 3.10 以上；Windows 10/11", "本机部署与启动"],
                  ["Web 与数据", "fastapi、uvicorn、httpx", "接口服务与外部请求"],
                  ["文档解析", "pymupdf（PyMuPDF）", "PDF 文本、页面与图像解析"],
                  ["检索与图谱", "numpy、networkx", "矩阵计算与图结构辅助"],
                  ["出图", "matplotlib、pandas", "实验数据可视化"],
                  ["离线 OCR", "rapidocr-onnxruntime、pillow", "扫描件识别与图像处理"],
                  ["导出与文档", "markdown、openpyxl、python-docx", "Markdown/Excel/Word 导出"],
              ], [2.6 * cm, 6.6 * cm, 7.0 * cm], "表 5　环境与主要依赖",
                  align=["tdc", "td", "td"])]

    doc.multiBuild(story, maxPasses=4)
    print("pages:", doc.page, "size:", Path(out_path).stat().st_size)
    return doc.page


if __name__ == "__main__":
    PAGE_HINT = build(ROOT / "docs" / "_probe_tech.pdf")
    build()
