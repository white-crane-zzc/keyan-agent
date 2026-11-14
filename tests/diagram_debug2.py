"""逐 token 调试 flowchart 解析。"""
import json
import subprocess
import time
from pathlib import Path

import httpx
import websocket

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
OUT = Path(r"E:\项目\科研小助手\data")
PORT = 9228

proc = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", f"--remote-debugging-port={PORT}",
                         f"--user-data-dir={OUT / 'edge_prof5'}", "--window-size=1600,1100",
                         "http://127.0.0.1:8000/"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
        print("异常:", json.dumps(res["exceptionDetails"], ensure_ascii=False)[:400])
    return res.get("result", {}).get("value")


time.sleep(4)
expr = r"""
(() => {
  const src = "flowchart TD\nA[输入] --> B[分词]\nB --> C[编码器堆叠]\nC --> D[分类头]";
  const shape = /^([A-Za-z0-9_\u4e00-\u9fff]+)\s*(?:\[([^\]]*)\]|\(([^)]*)\)|\{([^}]*)\})?$/;
  const rows = src.split('\n').map(l => l.trim()).filter(Boolean);
  const info = [];
  for (const line of rows) {
    if (/^(flowchart|graph)\s+/i.test(line)) { info.push([line, 'dir']); continue; }
    const parts = line.split(/\s*(?:-->|==>|-.->)\s*(?:\|[^|]*\|)?/).map(s => s.trim()).filter(Boolean);
    info.push([line, parts.map(p => [p, !!p.match(shape)])]);
  }
  return JSON.stringify(info);
})()
"""
print(js(expr))
ws.close()
proc.terminate()
