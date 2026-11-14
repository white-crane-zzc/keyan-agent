"""图谱页视觉复检：1600x1100 抓整页截图。"""
import base64
import json
import subprocess
import time
from pathlib import Path

import httpx
import websocket

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
OUT = Path(r"E:\项目\科研小助手\data")
PORT = 9227


def main():
    proc = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", f"--remote-debugging-port={PORT}",
                             f"--user-data-dir={OUT / 'edge_prof4'}", "--window-size=1600,1100",
                             "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = None
    for _ in range(40):
        try:
            tabs = httpx.get(f"http://127.0.0.1:{PORT}/json", timeout=2).json()
            page = [t for t in tabs if t["type"] == "page"][0]
            ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=30)
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
                return msg.get("result", {})

    def js(expr):
        return call("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)

    call("Page.enable")
    call("Network.enable")
    call("Network.setCacheDisabled", cacheDisabled=True)
    call("Page.navigate", url=f"http://127.0.0.1:8000/?t={int(time.time())}")
    time.sleep(4)
    # 勾 1 篇（Attention），验证单篇自动扩邻居的提示与画面
    js("Array.from(document.querySelectorAll('.chip')).find(c=>c.dataset.id==='1').click()")
    js("document.querySelector('#tab-graph') || document.querySelector('[data-tab=graph]')")
    js("""(() => { const b=[...document.querySelectorAll('nav a, nav button, .tab')].find(x=>x.textContent.trim()==='图谱'); if(b) b.click(); return !!b; })()""")
    time.sleep(1)
    js("document.querySelector('#btnBuildGraph').click()")
    time.sleep(4)
    info = js("""JSON.stringify({note: document.querySelector('#graphNote').textContent,
       nodes: document.querySelectorAll('#graphSvg g').length,
       core: document.querySelectorAll('#coreList li').length})""")
    print("单篇:", info["result"]["value"])
    shot = call("Page.captureScreenshot", format="png", captureBeyondViewport=True)
    (OUT / "graph_single.png").write_bytes(base64.b64decode(shot["data"]))
    js("Array.from(document.querySelectorAll('.chip.on')).forEach(c=>c.click())")
    js("document.querySelector('#btnBuildGraph').click()")
    time.sleep(4)
    info2 = js("JSON.stringify({note: document.querySelector('#graphNote').textContent, nodes: document.querySelectorAll('#graphSvg g').length})")
    print("全库:", info2["result"]["value"])
    shot = call("Page.captureScreenshot", format="png", captureBeyondViewport=True)
    (OUT / "graph_all.png").write_bytes(base64.b64decode(shot["data"]))
    ws.close()
    proc.terminate()


main()
