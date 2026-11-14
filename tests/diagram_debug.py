"""直接在页面里跑 renderFlowchart，定位解析问题。"""
import json
import subprocess
import time
from pathlib import Path

import httpx
import websocket

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
OUT = Path(r"E:\项目\科研小助手\data")
PORT = 9228

src = "flowchart TD\\n    A[输入] --> B[分词]\\n    B --> C[编码器堆叠]\\n    C --> D[分类头]"

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
        print("异常:", json.dumps(res["exceptionDetails"], ensure_ascii=False)[:500])
    return res.get("result", {}).get("value")


call("Page.enable")
call("Network.setCacheDisabled", cacheDisabled=True)
call("Page.navigate", url=f"http://127.0.0.1:8000/?t={int(time.time())}")
time.sleep(4)
print("typeof:", js("typeof renderFlowchart"))
print("返回:", js(f"renderFlowchart('{src}', document.querySelector('#diagramPreview'))"))
print("rect:", js("document.querySelectorAll('#diagramPreview rect').length"),
      "line:", js("document.querySelectorAll('#diagramPreview line').length"))
print("svg预览:", js("document.querySelector('#diagramPreview').innerHTML.slice(0,200)"))
ws.close()
proc.terminate()
