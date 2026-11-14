"""写作页视觉复检：架构图直接出框图 + 示例 CSV 下载。"""
import base64
import json
import subprocess
import time
from pathlib import Path

import httpx
import websocket

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
OUT = Path(r"E:\项目\科研小助手\data")
PORT = 9228


def main():
    proc = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", f"--remote-debugging-port={PORT}",
                             f"--user-data-dir={OUT / 'edge_prof5'}", "--window-size=1600,1100",
                             "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = None
    for _ in range(40):
        try:
            tab = [t for t in httpx.get(f"http://127.0.0.1:{PORT}/json", timeout=2).json() if t["type"] == "page"][0]
            ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=30)
            break
        except Exception:
            time.sleep(0.5)
    mid = [0]

    def call(method, **params):
        mid[0] += 1
        ws.send(json.dumps({"id": mid[0], "method": method, "params": params}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == mid[0]:
                return msg

    def js(expr):
        r = call("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        res = r.get("result", {})
        if "exceptionDetails" in res:
            print("JS 异常:", res["exceptionDetails"].get("text"), res["exceptionDetails"].get("exception", {}).get("description", "")[:300])
        return res.get("result", {}).get("value")

    call("Page.enable")
    call("Network.enable")
    call("Network.setCacheDisabled", cacheDisabled=True)
    # 允许下载
    call("Page.setDownloadBehavior", behavior="allow", downloadPath=str(OUT / "dl"))
    call("Page.navigate", url=f"http://127.0.0.1:8000/?t={int(time.time())}")
    time.sleep(4)

    js("[...document.querySelectorAll('nav a,nav button,.tab')].find(x=>x.textContent.trim()==='写作').click()")
    time.sleep(1)
    js("document.querySelector('#diagramDesc').value='输入→分词→Transformer 编码器堆叠→分类头'")
    js("document.querySelector('#btnDiagram').click()")
    for _ in range(40):
        time.sleep(2)
        done = js("document.querySelector('#diagramPreview svg') ? 'svg' : document.querySelector('#diagramOut').textContent.slice(0,6)")
        if done == "svg":
            break
    print("框图:", js("""JSON.stringify({boxes: document.querySelectorAll('#diagramPreview rect').length,
        lines: document.querySelectorAll('#diagramPreview line').length,
        text: document.querySelector('#diagramOut').textContent.slice(0,40)})"""))
    shot = call("Page.captureScreenshot", format="png", captureBeyondViewport=True)
    (OUT / "write_diagram.png").write_bytes(base64.b64decode(shot["result"]["data"]))

    # 示例 CSV 下载
    js("document.querySelector('#btnSampleCsv').click()")
    time.sleep(3)
    dl = OUT / "dl" / "示例数据.csv"
    print("示例 CSV:", dl.exists(), dl.stat().st_size if dl.exists() else 0)
    if dl.exists():
        print("内容:", dl.read_text(encoding="utf-8").replace("\n", " | "))

    # 把下载的 CSV 塞进 file input，真跑一次绘图
    if dl.exists():
        r = call("Runtime.evaluate", expression="document.querySelector('#csvInput').outerHTML")
        node = call("DOM.getDocument")
        root = node["result"]["root"]["nodeId"]
        found = call("DOM.querySelector", nodeId=root, selector="#csvInput")
        if found.get("result", {}).get("nodeId"):
            try:
                call("DOM.setFileInputFiles", nodeId=found["result"]["nodeId"],
                     files=[str(dl).replace("\\", "/")])
                js("document.querySelector('#plotDesc').value='不同模型 BLEU 对比'")
                js("document.querySelector('#plotKind').value='bar'")
                js("document.querySelector('#btnPlot').click()")
                for _ in range(20):
                    time.sleep(2)
                    if js("!!document.querySelector('#plotOut img')"):
                        break
                print("绘图结果:", js("JSON.stringify({img: (document.querySelector('#plotOut img')||{}).src || null, hint: document.querySelector('#plotOut').textContent.slice(0,120)})"))
            except Exception as e:
                print("设置文件失败:", e)
        shot2 = call("Page.captureScreenshot", format="png", captureBeyondViewport=True)
        (OUT / "write_plot.png").write_bytes(base64.b64decode(shot2["result"]["data"]))
    ws.close()
    proc.terminate()


main()
