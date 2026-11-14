# -*- coding: utf-8 -*-
"""生成《科研小助手 Agent 作品介绍文档》。"""
from pathlib import Path

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, Image as RLImage, KeepTogether,
                               PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle)

ROOT = Path(r"E:\项目\科研小助手")
DATA = ROOT / "data"
OUT = ROOT / "docs" / "科研小助手Agent-作品介绍文档.pdf"

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
}
DOCTITLE = "科研小助手 Agent　作品介绍文档"


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


TMP = ROOT / "docs" / "_tmp_figs"


def _trim(path):
    """裁掉截图四周的纯白留白，避免图片被大面积空白挤小。"""
    TMP.mkdir(parents=True, exist_ok=True)
    out = TMP / (Path(path).stem + "_trim.png")
    with Image.open(path) as im:
        rgb = im.convert("RGB")
        gray = rgb.convert("L")
        w, h = gray.size
        bbox = gray.point(lambda v: 255 if v < 246 else 0).getbbox()
        if not bbox:
            rgb.save(out)
            return out
        left, top, right, bottom = bbox
        pad = 10
        crop = rgb.crop((max(0, left - pad), max(0, top - pad),
                         min(w, right + pad), min(h, bottom + pad)))
        crop.save(out)
        return out


def figure(path, cap, max_h=8.9):
    path = _trim(path)
    with Image.open(path) as im:
        w_px, h_px = im.size
    width = 15.6 * cm
    height = width * h_px / w_px
    if height > max_h * cm:
        height = max_h * cm
        width = height * w_px / h_px
    return KeepTogether([RLImage(str(path), width=width, height=height),
                         Paragraph(cap, S["cap"])])


class Doc(BaseDocTemplate):
    def __init__(self, path):
        BaseDocTemplate.__init__(self, path, pagesize=A4, leftMargin=2.2 * cm,
                                 rightMargin=2.2 * cm, topMargin=2.3 * cm, bottomMargin=2.1 * cm,
                                 title="科研小助手 Agent 作品介绍文档", author="科研小助手 Agent")
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


def build(out_path=OUT):
    doc = Doc(str(out_path))
    story = []

    # 封面
    story += [Spacer(1, 4.6 * cm),
              P("科研小助手 Agent", "ct"),
              P("面向科研论文全流程的解析、问答、图谱与写作辅助系统", "cs"),
              Spacer(1, 0.8 * cm),
              P("作品介绍文档", "ct"),
              Spacer(1, 1.4 * cm)]
    meta = Table([[Paragraph(a, S["cm"]), Paragraph(b, S["cm"])] for a, b in [
        ("参赛赛事", "全国计算机应用能力与数字素养大赛暨第九届传智杯 AI 大模型创新应用挑战赛（省赛）"),
        ("作品形态", "本地部署的 Web 应用（FastAPI + SQLite + 原生前端）"),
        ("模型接入", "OpenAI 兼容接口，可插拔（默认 DeepSeek，可指向本机 Ollama）"),
        ("文档内容", "项目详情与使用方式、项目亮点、关键技术、实测情况、运行截图"),
        ("配套文件", "同名《技术文档》、源码包与公开仓库"),
        ("提交日期", "2026 年 11 月"),
    ]], colWidths=[2.8 * cm, 12.6 * cm], hAlign="CENTER")
    meta.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (0, -2), 0.4, colors.HexColor("#dcdcdc")),
        ("LINEBELOW", (1, 0), (1, -2), 0.4, colors.HexColor("#dcdcdc")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
    ]))
    story += [meta, PageBreak()]

    # 一 项目详情
    story += [H1("一、项目详情"),
              P("科研小助手 Agent 是一个本地运行的科研论文辅助系统。它把“把论文存进来—读懂它—问它问题—看清论文之间的关系—照着它写初稿—追踪新论文”这几件事串成一条完整流水线，"
                "而不是把若干互不相干的 AI 功能拼在一个页面上。系统以一篇 PDF 为起点，自动完成结构解析、去重入库、检索增强问答、引用网络构建与写作素材生成，全部结果在同一个界面内连续使用。"),
              P("它解决的问题很具体：科研新手真正卡住的地方往往不是“不会用大模型”，而是论文太多、英文太长，逐篇精读的时间成本极高；通用聊天模型回答论文问题时给不出可核对的原文位置，"
                "无法直接用于写作；“这几篇之间谁引了谁、哪篇是绕不开的基石”这类关系问题，靠人脑记不住，靠聊天模型又容易编。系统用“原文证据 + 结构化数据”两个抓手应对：所有回答都带页码与章节引用，"
                "所有引用关系都来自解析出的参考文献条目，而不是模型记忆。"),
              P("首屏可见的形态是六个页签——文库、阅读、问答、图谱、写作、推荐，对应“入库—精读—提问—看关系—写初稿—追踪新论文”六个动作。当前演示库共 27 篇论文、"
                "22214 个文本块、2369 条参考文献条目，引用图谱含 27 个节点、92 条有向边，覆盖 Attention、BERT、GPT 系列及其后的主流大模型技术路线，是一个可直接上手操作的真实库，不是空壳演示。"),
              H2("（一）使用方式"),
              P("环境要求为 Windows 10/11 与 Python 3.10 及以上。拿到压缩包后按四步操作：", "item"),
              P("第一步，安装 Python 3.10 以上版本，安装时勾选“Add Python to PATH”；第二步，解压到任意目录；第三步，双击根目录的 启动.cmd，脚本自动创建虚拟环境并按 requirements.txt 安装依赖，"
                "首次需联网，耗时约五到十分钟；第四步，浏览器打开 127.0.0.1:8000，文库页显示 27 篇论文即部署成功。", "item"),
              P("需要使用大模型问答与翻译时，把 .env.example 复制为 .env，填入接口地址、模型名与密钥后重启即可；不填时以原文证据模式运行，功能不中断。包内不附带 .env，"
                "密钥由使用者自行配置，避免明文密钥随包分发。", "item"),
              P("源码获取有两种方式，效果相同：一是解压随作品提交的 keyan-agent-code-1.0.zip；二是克隆公开仓库 github.com/white-crane-zzc/keyan-agent。"
                "仓库版不含库数据与论文原件，首次启动为空库，需自行入库，其余步骤一致。", "item")]
    story += [H2("（二）六个页签的操作"),
              table([
                  ["页签", "解决的问题", "主要操作"],
                  ["文库", "批量入库与重复判定", "拖拽或选择多个 PDF 上传，也可粘贴 arXiv 编号下载；上传后给出解析摘要与判重结果，重复时并列展示差异，由使用者决定跳过、并存或替换"],
                  ["阅读", "原文、译文与引用跳转", "左侧按页渲染原始版面，右侧按章节列出文本块；点击段落逐段翻译，可开中英对照；正文 [n] 上标点击跳到参考文献并高亮，参考文献可“返回正文”；整篇导出 Markdown 或 HTML"],
                  ["问答", "带出处的检索增强回答", "勾选参与检索的论文（不勾选则全库），答案下方列引用片段、页码与章节；模型不可用时自动切换原文证据模式"],
                  ["图谱", "引用网络与核心论文", "一键生成全库引用网络；只勾一篇时自动补入其直接引用邻居；右侧列出基石论文、边缘论文与被引最多的外部工作，并可生成领域综述"],
                  ["写作", "框架、架构图与实验图表", "一句研究想法生成含摘要至结论的框架，参考文献只从勾选清单中选取；Mermaid 在页面内渲染为框图，另可导出 TikZ、Graphviz 源码；上传 CSV/XLSX 生成折线、柱状、雷达图并配中英文图注"],
                  ["推荐", "追踪新论文", "按文库主题抓取 arXiv 最新论文并按摘要重合度排序，可一键下载入库或标记有用/不相关，反馈写回数据库；后台每 6 小时自动刷新"],
              ], [1.7 * cm, 4.2 * cm, 10.3 * cm], "表 1　六个页签的职责与操作",
                  align=["tdc", "td", "td"]),
              P("一次完整使用可概括为七步：文库上传论文并确认解析摘要与判重结论；阅读页核对解析质量、按需翻译或导出；问答页勾选论文提问并用答案中的页码回原文核对；"
                "图谱页生成引用网络找出基石与边缘论文；写作页输入研究想法生成框架；写作页上传实验数据生成图表；推荐页查看新论文并按需入库。")]

    # 二 亮点
    story += [H1("二、项目亮点"),
              H2("（一）原文证据是默认态，而不是兜底"),
              P("每条回答都附带命中片段的页码与章节，可直接回原文核对；模型不可用、额度用尽或网络不通时系统不报错，而是返回带出处的原文片段。这让演示与答辩不依赖网络状态，也让回答始终可核查。"),
              H2("（二）解析器按论文排版规律设计，而非套用通用提取"),
              P("通用提取会把“1”与“Introduction”拆成两段、把正文句子误判为标题、把参考文献之后的附录整段丢弃。本系统按编号深度定层级，先合并编号块与紧随其后的标题块，再按“1 为一级、1.1 为二级”赋层级；"
                "首页按行聚类重排解决双栏作者与单位错位；参考文献之后若出现字号明显大于正文的短行即判为附录起点，其后内容仍按正文入库；表格单独成块并在检索时豁免数字占比降权。实测这一处修复使 BERT 的入库文本块由 153 增至 328。"),
              H2("（三）三信号判重，把决定权交回使用者"),
              P("同一篇论文的 v1 与 v7 版本首页多一行授权声明、换行方式也不同，单靠文本指纹相似度只有 0.75 会漏判。系统改为标题相似度、摘要前 320 字相似度、首作者前两词命中三信号联合判断，"
                "满足任一组合条件即判为重复，并把差异项列给使用者。实测同一篇论文两个版本判定为重复、相似度 0.954。"),
              H2("（四）引用图谱不依赖额外科学计算包，结论可解释"),
              P("PageRank 由矩阵幂迭代自行实现（阻尼系数 0.85、迭代 60 次），不依赖网络分析库的科学计算依赖；“基石论文”收紧为入度大于零且等于全图最大值，避免“被引 0 却被标成基石”；"
                "只勾一篇时自动补入其直接引用邻居，不给出孤立节点。"),
              H2("（五）跨语言检索的四层处理与一次解析多次复用"),
              P("中文提问、英文论文时词面匹配几乎无效：内置约 45 组中英术语映射做查询扩展，再由模型把中文问题压成英文检索式，候选片段按语义重排取前 8 条，多路召回按篇配额合并，"
                "保证长论文不被短论文挤占；参考文献条目单独建块并以较低权重参与检索，避免被引文带偏。同一份解析结果同时支撑阅读、问答、图谱、综述、写作五类功能，图表与导出文件全部本地生成，"
                "既不重复调用模型，也不依赖第三方渲染服务。")]

    # 三 关键技术
    story += [H1("三、项目中涉及的关键技术"),
              P("以下七项是系统真正的技术支点，展开的技术说明与选型理由见配套《技术文档》第四、五章。"),
              table([
                  ["关键技术", "作用", "在系统中的位置"],
                  ["结构感知 PDF 解析", "按论文排版规律还原标题层级、作者单位、表格、参考文献与附录，输出带页码与章节的结构化文本块", "parser.py：编号定层级、首页行聚类、附录截断、表格独立成块"],
                  ["三信号内容判重", "识别同篇论文的不同版本，输出差异项交使用者决策", "pipeline.py：标题 / 摘要前 320 字 / 首作者三信号联合"],
                  ["检索增强问答（RAG）", "回答限定在检索到的原文片段内，并逐条标注页码与章节", "search.py + llm.py：术语扩展、多路召回、按篇配额、模型重排"],
                  ["中文提问检英文论文的跨语言检索", "解决词面错配，让中文问题能在英文原文中命中", "约 45 组术语映射 + 模型生成英文检索式 + 语义重排"],
                  ["自实现 PageRank 引用图谱", "算清库内论文的引用关系，识别基石与边缘论文", "graph.py：矩阵幂迭代（阻尼 0.85、60 次），角色判定条件随接口返回"],
                  ["离线扫描件 OCR", "扫描版论文也能入库并定位到原文坐标", "parser.py + rapidocr：逐页检测文本量，低于 40 字符按 200 dpi 识别并回填坐标"],
                  ["本地出图与文档生成", "架构图、数据图、Markdown / HTML 导出全部在本机完成，论文内容不出本机", "前端 Mermaid 渲染 + matplotlib 出图 + 服务端导出"],
              ], [3.2 * cm, 6.0 * cm, 7.0 * cm], "表 2　七项关键技术",
                  align=["td", "td", "td"])]

    # 四 AI 落地
    story += [H1("四、AI 测试技术落地使用情况概述"),
              P("系统的 AI 能力不是“接个模型就完事”，而是按“能不能被验证”逐项落地：问答与翻译接大模型，检索、图谱、判重、坐标回填等关键结论则由确定性代码计算，"
                "模型只负责语言组织与排序。测试分接口级、界面级、干净环境级三层推进，关键数据见表 3。"),
              table([
                  ["测试项", "方法", "结果"],
                  ["库规模", "GET /api/status", "27 篇论文、22214 个文本块、2369 条参考文献条目"],
                  ["引用图谱", "POST /api/graph 全库", "27 个节点、92 条有向边，基石识别为 BERT"],
                  ["问答准确性", "9 道样例题比对", "6 道命中并给出正确页码，3 道未达标"],
                  ["接口可用性", "逐接口打点", "状态、文库、图谱、问答、推荐、翻译、导出均返回 200；未配置模型时按设计降级为原文证据"],
                  ["扫描件 OCR", "4 页扫描版 PDF", "离线识别与坐标回填成功，耗时 38.2 秒"],
                  ["长文档压力", "540 页合成长文档", "解析与入库完成，未出现内存或超时中断"],
                  ["干净环境复现", "本机新解压 + 全新虚拟环境", "依赖安装成功、服务启动、库数据完整、六页签可用（未在第二台物理机器复测）"],
              ], [2.5 * cm, 4.6 * cm, 9.1 * cm], "表 3　AI 能力实测数据",
                  align=["tdc", "td", "td"]),
              P("未达标的 3 道样例题如实说明：两道是数值型问题（表格里的 BLEU 值、GPT-1 参数量）因纯词面检索召回偏弱而未命中，一道是原文本身未给出对应数值、系统回答“材料未提及”。"
                "前两道的根因已定位，改进方向是引入本地嵌入模型补向量召回；这类结论不修饰、也不删减。")]

    # 五 图片
    story += [H1("五、项目相关图片")]
    P("以下七张均为系统实际运行截图，非示意图，取自同一台机器同一轮使用，覆盖六个页签；截图中顶栏显示“模型已就绪 · deepseek-chat · 论文 27 篇”，与正文实测数字一致。")
    shots = [
        (DATA / "fig_library.png", "图 1　文库页：PDF 上传区与按 arXiv 编号下载入口，下方为我的文库；顶栏显示模型与服务状态"),
        (DATA / "fig_reader.png", "图 2　阅读页三栏：左为章节大纲导航，中为原始版面（第 1/15 页），右为译文面板；顶部为翻译本页／翻译全文、导出 Markdown／HTML、中英对照"),
        (DATA / "fig_qa.png", "图 3　问答页：按勾选论文作答，答案给出作者列表，答案后逐条附引用，每条含论文名、页码与章节"),
        (DATA / "fig_graph.png", "图 4　引用图谱：选定论文后的局部图谱（全库规模为 27 节点 92 边，见表 3），右侧列出枢纽论文、边缘论文与被引最多的外部工作"),
        (DATA / "fig_write1.png", "图 5　写作页框架生成：左侧按清单文献输出 Abstract 到 Related Work 的结构化框架，右侧把“输入—分词—编码器堆叠—分类头”即时渲染为架构图"),
        (DATA / "fig_write2.png", "图 6　实验数据可视化：上传 CSV 后由服务端出图，自动生成中英文图注与数据摘要，并给出图内数值统计"),
        (DATA / "fig_recommend.png", "图 7　推荐页：按库内主题抓取 arXiv 最新论文，标注发布日、相关度与共享关键词，可一键下载入库或标记有用／不相关"),
    ]
    for path, cap in shots:
        if path.exists():
            story += [figure(path, cap)]

    # 六 获奖
    story += [H1("六、项目之前是否发表过或获奖"),
              P("截至本次提交，本项目未曾公开发表，也未获得任何奖项或参加过其他赛事评审，属首次以完整形态对外提交。三点补充说明："
                "系统内论文均来自公开论文源（arXiv 与公开出版物），仅用于本地演示与测评，不随作品再分发；代码与文档均为自行开发，未直接复用他人项目源码，第三方依赖在《技术文档》附录逐项列出；"
                "本文件、《技术文档》与源码包均为此前未在任何渠道公开的内容。")]

    # 七 优化
    story += [H1("七、在其他项目基础上的优化"),
              P("本项目并非从零起步，其基础是作者在赛前自行开发的同名内测版本（仅本地使用、未公开）。内测版已具备解析、检索问答与基本界面，但在真实使用与答辩演练中暴露了若干问题，"
                "本次提交的版本是在该基础上有针对性地迭代而成，优化集中在解析质量、两个页签的可用性、部署可移植性与失败降级设计四个方面。"),
              table([
                  ["优化项", "内测版状态", "本次优化", "验证方式"],
                  ["图谱角色判定", "只取排名首位，出现“被引 0 却标为基石”", "改为入度大于零且等于最大值，单篇时补入直接引用邻居", "全库生成后核对基石为 BERT，27 节点 92 边"],
                  ["写作页架构图", "Mermaid 源码以纯文本显示", "前端解析渲染为框图，另可导出 TikZ、Graphviz", "界面实测出图"],
                  ["实验数据可视化", "上传数据后图表区空白", "服务端 matplotlib 出图、注册中文字体、自动配中英文图注", "上传示例数据出图"],
                  ["扫描件 OCR", "依赖未列入安装清单，换机后不可用", "统一依赖来源至 requirements.txt，启动脚本按清单安装", "干净环境从零安装后复测 OCR"],
                  ["依赖清单", "启动脚本内手写依赖，与清单两处维护且不一致", "安装命令统一读取 requirements.txt，单一来源", "逐项核对安装输出"],
                  ["交付包内容", "含演示视频、成品文档与演示数据，113.5 MB", "剔除演示视频与成品文档，压至 78.3 MB", "解压清点 72 个文件，库与论文完整"],
                  ["上手指引", "仅有面向开发者的说明", "新增“拿到压缩包后如何运行”四步指引与已验证结论", "按指引在干净环境复现"],
              ], [2.4 * cm, 4.6 * cm, 5.6 * cm, 3.6 * cm], "表 4　相对内测版的优化内容",
                  align=["tdc", "td", "td", "td"]),
              P("以上改动均由真实问题驱动：每一条都先复现、再定位、再修复，修复后用脚本或界面重新验证。内测版遗留的数值型检索偏弱、单用户设计、无鉴权等边界，在本次版本中仍然存在，"
                "已在《技术文档》第六章如实列出并列入后续计划。")]

    # 八 文件说明
    story += [H1("八、作品文件与提交说明"),
              table([
                  ["作品文件", "内容", "获取方式"],
                  ["源码包", "keyan-agent-code-1.0.zip：72 个文件、78.3 MB，含全部源码、库数据（27 篇论文与解析结果）、论文原件、自测脚本与文档源文件；不含演示视频与成品文档", "网盘分享链接，附提取码"],
                  ["公开仓库", "github.com/white-crane-zzc/keyan-agent（Public），与源码包同源，可查完整提交历史", "浏览器直接访问"],
                  ["作品介绍文档", "本文件：项目详情、亮点、关键技术、实测情况与七张运行截图", "随作品文件提交"],
                  ["技术文档", "《科研小助手 Agent 技术文档》：系统架构、AI 技术方案、核心功能、测试与部署，共 10 页", "随作品文件提交"],
                  ["演示视频", "5 至 8 分钟、MP4、不低于 1080p，普通话讲解配中文字幕，覆盖项目介绍、核心功能演示与 AI 技术亮点", "公开视频平台链接（https 开头）"],
                  ["在线演示", "不提供：系统为单机本地部署且未做鉴权，开放公网有被删库风险", "—"],
              ], [2.6 * cm, 9.4 * cm, 4.2 * cm], "表 5　作品文件一览",
                  align=["tdc", "td", "td"])]

    doc.build(story)
    print("pages:", doc.page, "size:", Path(out_path).stat().st_size)
    return doc.page


if __name__ == "__main__":
    build()
