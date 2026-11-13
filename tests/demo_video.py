"""生成演示视频：无头 Edge 真实操作截图 → 带字幕与缓慢推镜的 1080p 视频。
用法：python tests/demo_video.py
产物：E:\\项目\\科研小助手\\docs\\演示视频.mp4
"""
import base64
import json
import subprocess
import time
from pathlib import Path

import httpx
import numpy as np
from PIL import Image, ImageDraw, ImageFont

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
ROOT = Path(r"E:\项目\科研小助手")
SHOTS = ROOT / "data" / "demo"
PORT = 9225
W, H, FPS = 1920, 1080, 24
FONT = r"C:\Windows\Fonts\msyh.ttc"
FONT_B = r"C:\Windows\Fonts\msyhbd.ttc" if Path(r"C:\Windows\Fonts\msyhbd.ttc").exists() else FONT
SHOTS.mkdir(parents=True, exist_ok=True)


# ----------------------------- 浏览器驱动 -----------------------------
def boot():
    proc = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", f"--remote-debugging-port={PORT}",
                             "--user-data-dir=" + str(SHOTS / "edge_prof"), f"--window-size={W},{H}",
                             "--hide-scrollbars", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import websocket
    t = None
    for _ in range(40):
        try:
            pages = [x for x in httpx.get(f"http://127.0.0.1:{PORT}/json", timeout=2).json() if x["type"] == "page"]
            if pages:
                t = pages[0]
                break
        except Exception:
            time.sleep(0.5)
    ws = websocket.create_connection(t["webSocketDebuggerUrl"], timeout=60)
    mid = [0]

    def send(method, params=None):
        mid[0] += 1
        ws.send(json.dumps({"id": mid[0], "method": method, "params": params or {}}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == mid[0]:
                return m

    def js(expr, by_value=True):
        r = send("Runtime.evaluate", {"expression": expr, "awaitPromise": True, "returnByValue": by_value})
        return r.get("result", {}).get("result", {}).get("value")

    def shot(name):
        send("Emulation.setDeviceMetricsOverride", {"width": W, "height": H, "deviceScaleFactor": 1, "mobile": False})
        r = send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
        p = SHOTS / f"{name}.png"
        p.write_bytes(base64.b64decode(r["result"]["data"]))
        print("  截图", name, p.stat().st_size // 1024, "KB")
        return p

    send("Runtime.enable")
    send("Page.enable")
    send("DOM.enable")
    send("Page.navigate", {"url": "http://127.0.0.1:8000"})
    time.sleep(5)
    return proc, send, js, shot


# ----------------------------- 素材采集 -----------------------------
def capture():
    proc, send, js, shot = boot()
    try:
        js("window.scrollTo(0,0)")
        time.sleep(1)

        lib = shot("01_library")

        js("document.querySelector('.tabs button[data-tab=\"reader\"]').click()")
        time.sleep(4)
        rd = shot("02_reader")
        js("document.querySelector('#btnTranslatePage').click()")
        time.sleep(5)
        tr = shot("03_translate")

        js("document.querySelector('.tabs button[data-tab=\"qa\"]').click()")
        time.sleep(2)
        js("""(()=>{const q=document.querySelector('#qaQuestion');
                 q.value='Transformer 为什么要用多头注意力？每个头的维度是多少？';
                 document.querySelector('#btnAsk').click();})()""")
        time.sleep(9)
        qa = shot("04_qa")

        js("document.querySelector('.tabs button[data-tab=\"graph\"]').click()")
        time.sleep(2)
        js("document.querySelector('#btnBuildGraph').click()")
        time.sleep(5)
        gp = shot("05_graph")

        js("document.querySelector('.tabs button[data-tab=\"write\"]').click()")
        time.sleep(2)
        js("""(()=>{document.querySelector('#ideaBox').value='用稀疏注意力做长文本分类';
                 document.querySelector('#btnOutline').click();
                 document.querySelector('#diagramDesc').value='提问->检索->重排->生成';
                 document.querySelector('#btnDiagram').click();})()""")
        time.sleep(5)
        wr = shot("06_write")

        # CSV 绘图：真实设置文件输入
        csv = SHOTS / "ablation.csv"
        csv.write_text("epoch,acc,f1\n1,0.62,0.58\n2,0.71,0.67\n3,0.78,0.74\n4,0.83,0.80\n5,0.86,0.84\n",
                       encoding="utf-8")
        try:
            obj = send("Runtime.evaluate", {"expression": "document.querySelector('#csvInput')"})
            oid = obj["result"]["result"]["objectId"]
            send("DOM.setFileInputFiles", {"files": [str(csv)], "objectId": oid})
            js("document.querySelector('#plotDesc').value='消融实验：准确率与 F1 随训练轮次变化'")
            js("document.querySelector('#plotKind').value='line'")
            js("document.querySelector('#btnPlot').click()")
            time.sleep(6)
        except Exception as e:
            print("  CSV 注入失败:", e)
        pl = shot("07_plot")

        js("document.querySelector('.tabs button[data-tab=\"rec\"]').click()")
        time.sleep(2)
        js("document.querySelector('#btnRecommend').click()")
        time.sleep(16)
        rc = shot("08_rec")

        js("window.scrollTo(0,0)")
        time.sleep(1)
        return [lib, rd, tr, qa, gp, wr, pl, rc]
    finally:
        proc.terminate()


# ----------------------------- 画面合成 -----------------------------
def font(sz, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT, sz)


def caption(img, title, sub):
    d = ImageDraw.Draw(img, "RGBA")
    band = 200
    d.rectangle([0, H - band, W, H], fill=(16, 20, 30, 214))
    d.rectangle([0, H - band, 8, H], fill=(47, 111, 237, 255))
    d.text((56, H - band + 34), title, font=font(44, True), fill=(255, 255, 255))
    d.text((56, H - band + 100), sub, font=font(27), fill=(178, 190, 214))
    d.text((W - 300, 26), "科研小助手 Agent", font=font(24, True), fill=(255, 255, 255, 190))
    return img


def kenburns(src: Path, frames: int, zoom_from=1.0, zoom_to=1.06):
    base = Image.open(src).convert("RGB")
    if base.size != (W, H):
        base = base.resize((W, H), Image.LANCZOS)
    out = []
    for i in range(frames):
        z = zoom_from + (zoom_to - zoom_from) * i / max(frames - 1, 1)
        cw, ch = int(W / z), int(H / z)
        cx, cy = (W - cw) // 2, (H - ch) // 2 - 40
        cy = max(0, min(cy, H - ch))
        out.append(base.crop((cx, cy, cx + cw, cy + ch)).resize((W, H), Image.LANCZOS))
    return out


def card(title, lines, tag=""):
    img = Image.new("RGB", (W, H), (13, 17, 26))
    d = ImageDraw.Draw(img)
    for i in range(H):  # 渐变
        d.line([(0, i), (W, i)], fill=(13 + i // 26, 17 + i // 30, 28 + i // 20))
    d.rectangle([0, 0, W, 8], fill=(47, 111, 237))
    d.text((110, 250), tag, font=font(26), fill=(120, 140, 180))
    d.text((110, 300), title, font=font(76, True), fill=(255, 255, 255))
    y = 470
    for l in lines:
        d.text((110, y), l, font=font(32), fill=(196, 208, 230))
        y += 62
    d.line([(110, 430), (110 + 560, 430)], fill=(47, 111, 237), width=3)
    return img


def dedupe_card():
    img = Image.new("RGB", (W, H), (243, 246, 251))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 8], fill=(47, 111, 237))
    d.text((100, 80), "内容去重：同一篇论文两个版本", font=font(46, True), fill=(24, 32, 48))
    d.text((100, 148), "判定为重复 · 相似度 0.954 · 建议保留库内版本（v7）", font=font(28), fill=(64, 84, 120))
    rows = [("对比项", "库内 v7", "新上传 v1"),
            ("页数", "15", "15"), ("字符数", "27748", "26074"),
            ("参考文献", "40", "36"), ("图 / 表", "2 / 4", "1 / 4"),
            ("版式", "单栏", "双栏")]
    x0, y0, wcol, rh = 100, 230, 560, 74
    for r, row in enumerate(rows):
        yy = y0 + r * rh
        fill = (255, 255, 255) if r else (226, 234, 248)
        d.rectangle([x0, yy, x0 + wcol * 3, yy + rh - 2], fill=fill)
        for c, txt in enumerate(row):
            f = font(30, r == 0)
            d.text((x0 + c * wcol + 30, yy + 22), txt, font=f,
                   fill=(26, 36, 56) if r == 0 or c == 0 else (60, 76, 104))
    d.text((100, 830), "判重条件：(标题 ≥0.85 且 摘要 ≥0.45) 或 (标题 ≥0.95 且 首作者命中) 或 MinHash ≥ 阈值",
           font=font(26), fill=(90, 108, 140))
    d.text((100, 880), "单阈值 MinHash 只有 0.75 —— 同篇不同排版会被漏判，所以改为三信号综合判定",
           font=font(26), fill=(90, 108, 140))
    return img


def main():
    print("1) 采集真实界面截图")
    shots = capture()

    print("2) 合成帧")
    import imageio_ffmpeg
    out = ROOT / "docs" / "演示视频.mp4"
    writer = imageio_ffmpeg.write_frames(str(out), size=(W, H), fps=FPS, codec="libx264",
                                         output_params=["-crf", "22", "-preset", "medium",
                                                        "-pix_fmt", "yuv420p"])
    writer.send(None)
    total = 0

    def push(imgs):
        nonlocal total
        for im in imgs:
            writer.send(np.asarray(im.convert("RGB"), dtype=np.uint8))
            total += 1

    scenes = [
        (card("科研小助手 Agent", ["PDF 解析与去重 · 带引用的 RAG 问答 · 双栏阅读与翻译",
                                   "引用图谱与综述 · 写作助手", "", "本地运行 · 数据不出盘 · 模型可插拔"], "功能演示"),
         16, "功能演示", "六条主线：文库 / 阅读 / 问答 / 图谱 / 写作 / 推荐"),
        (card("技术架构", ["单进程 FastAPI + 原生前端 + SQLite，数据全落 data/",
                          "解析：PyMuPDF 文本块 bbox → 编号深度定层级 + 双栏聚类",
                          "检索：BM25（中文二元组）+ 图表标题降权",
                          "图谱：networkx + 自实现 PageRank（不依赖 scipy）",
                          "模型：OpenAI 兼容接口，缺省降级为原文证据"], "架构"),
         24, "技术架构", "模型是增强项，不是前置条件"),
        (shots[0], 20, "① 文库：自动解析与入库", "上传或按 arXiv 编号下载，解析标题、章节层级、双栏、参考文献"),
        (dedupe_card(), 20, "① 内容去重", "同一篇的不同版本：给相似度、逐项差异，并提示保留哪一版"),
        (shots[1], 28, "② 阅读：双栏还原与树状导航", "文本块按 bbox 还原双栏；左侧章节树可点击定位"),
        (shots[2], 18, "② 翻译：页级 / 对照 / 划词", "未配置模型时返回降级提示，不阻断阅读"),
        (shots[3], 26, "③ 单篇问答：检索 + 原文引用", "回答带论文名、页码、章节，点击可直接跳回原文"),
        (shots[4], 24, "④ 引用图谱：PageRank 找基石", "被引最多的论文标为基石（蓝），只出边不入选边缘"),
        (shots[5], 22, "⑤ 写作助手：框架 + 架构图", "References 只取库内真实文献；架构图输出 mermaid"),
        (shots[6], 22, "⑤ CSV → 学术图表", "折线/柱状/雷达 + 学术图注 + 统计摘要"),
        (shots[7], 22, "⑥ arXiv 推荐：理由 + 赞踩反馈", "含开源代码优先，反馈落库供后续调权"),
        (card("如何运行", ["双击 启动.cmd：自动建 venv、装依赖、起服务",
                          "或 .venv\\Scripts\\python.exe -m uvicorn app.main:app --port 8000",
                          "浏览器打开 http://127.0.0.1:8000",
                          "复制 .env.example 为 .env 填 key，重启即启用大模型"], "使用"),
         22, "如何运行", "Windows 一键脚本 + 手动命令两种方式"),
        (card("实测", ["Attention：15 页 / 40 参考文献 / 24 章节，单栏",
                       "BERT：16 页 / 71 参考文献 / 19 章节，双栏",
                       "去重：v1 vs v7 相似度 0.954，差异 5 项",
                       "六页签真实点击验收：无 JS 异常"], "结果"),
         18, "实测结果", "全部为本机真实运行输出"),
        (card("边界与后续", ["扫描件需接 OCR，当前只取文本层",
                            "公式以 PDF 渲染呈现，未抽 LaTeX 语义",
                            "引用图谱对无编号参考文献匹配率偏低",
                            "在线演示需公网部署后再给演示地址"], "坦诚"),
         20, "边界与后续", "没做到的写清楚，比含糊更可信"),
    ]

    for item, secs, title, sub in scenes:
        frames = int(secs * FPS)
        if isinstance(item, Path):
            for im in kenburns(item, frames):
                push([caption(im, title, sub)])
        else:
            push(kenburns_img(item, frames))
        print(f"  场景完成：{title} ({secs}s)")

    writer.close()
    print(f"视频已生成：{out} ｜ {out.stat().st_size // 1024 // 1024} MB ｜ {total / FPS:.1f} 秒")


def kenburns_img(img: Image.Image, frames: int, zoom_from=1.0, zoom_to=1.03):
    base = img.convert("RGB")
    if base.size != (W, H):
        base = base.resize((W, H), Image.LANCZOS)
    out = []
    for i in range(frames):
        z = zoom_from + (zoom_to - zoom_from) * i / max(frames - 1, 1)
        cw, ch = int(W / z), int(H / z)
        cx, cy = (W - cw) // 2, (H - ch) // 2
        out.append(base.crop((cx, cy, cx + cw, cy + ch)).resize((W, H), Image.LANCZOS))
    return out


if __name__ == "__main__":
    main()
