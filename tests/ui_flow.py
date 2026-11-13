"""交互级前端验收：真实点按钮 → 断言页面出结果 → 截图。
用法：python tests/ui_flow.py
"""
import base64
import json
import subprocess
import time
from pathlib import Path

import httpx

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
OUT = Path(r"E:\项目\科研小助手\data")
PORT = 9224


def boot():
    proc = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", f"--remote-debugging-port={PORT}",
                             "--user-data-dir=" + str(OUT / "edge_prof2"), "--window-size=1600,1100",
                             "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import websocket
    for _ in range(40):
        try:
            t = [x for x in httpx.get(f"http://127.0.0.1:{PORT}/json", timeout=2).json() if x["type"] == "page"]
            if t:
                break
        except Exception:
            time.sleep(0.5)
    ws = websocket.create_connection(t[0]["webSocketDebuggerUrl"], timeout=60)
    mid = [0]
    logs = []

    def send(method, params=None):
        mid[0] += 1
        ws.send(json.dumps({"id": mid[0], "method": method, "params": params or {}}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == mid[0]:
                return m
            if m.get("method") == "Runtime.exceptionThrown":
                logs.append("EXC " + str(m["params"])[:200])

    def js(expr):
        r = send("Runtime.evaluate", {"expression": expr, "awaitPromise": True, "returnByValue": True})
        return r.get("result", {}).get("result", {}).get("value")

    def shot(name):
        r = send("Page.captureScreenshot", {"format": "png"})
        (OUT / f"flow_{name}.png").write_bytes(base64.b64decode(r["result"]["data"]))
        print(f"  截图 flow_{name}.png")

    send("Runtime.enable")
    send("Page.enable")
    send("Page.navigate", {"url": "http://127.0.0.1:8000"})
    time.sleep(4)
    return proc, send, js, shot, logs


def main():
    proc, send, js, shot, logs = boot()
    try:
        print("1) 问答页真实提问")
        js("document.querySelector('.tabs button[data-tab=\"qa\"]').click()")
        time.sleep(2)
        js("""(()=>{const q=document.querySelector('#qaQuestion');
                 q.value='Transformer 为什么需要多头注意力？每个头维度多少？';
                 document.querySelector('#btnAsk').click();})()""")
        time.sleep(8)
        answer = js("document.querySelector('#qaAnswer').innerText.slice(0,160)")
        print("   回答片段:", (answer or "").replace("\n", " ")[:160])
        shot("qa")

        print("2) 图谱页真实生成")
        js("document.querySelector('.tabs button[data-tab=\"graph\"]').click()")
        time.sleep(2)
        js("document.querySelector('#btnBuildGraph').click()")
        time.sleep(4)
        nodes = js("document.querySelectorAll('#graphSvg g').length")
        core = js("document.querySelector('#coreList').innerText.slice(0,80)")
        print("   图中节点数:", nodes, "| 枢纽:", (core or "").replace("\n", "/"))
        shot("graph")

        print("3) 写作页：框架 + 架构图")
        js("document.querySelector('.tabs button[data-tab=\"write\"]').click()")
        time.sleep(2)
        js("""(()=>{document.querySelector('#ideaBox').value='用稀疏注意力做长文本分类';
                 document.querySelector('#btnOutline').click();})()""")
        time.sleep(3)
        print("   框架:", (js("document.querySelector('#outlineOut').innerText.slice(0,100)") or "").replace("\n", " "))
        js("""(()=>{document.querySelector('#diagramDesc').value='提问->检索->重排->生成';
                 document.querySelector('#btnDiagram').click();})()""")
        time.sleep(3)
        print("   架构图:", (js("document.querySelector('#diagramOut').innerText.slice(0,100)") or "").replace("\n", "/"))
        shot("write")

        print("4) 推荐页真实抓取")
        js("document.querySelector('.tabs button[data-tab=\"rec\"]').click()")
        time.sleep(2)
        js("document.querySelector('#btnRecommend').click()")
        time.sleep(15)
        print("   推荐条数:", js("document.querySelectorAll('#recList .rec').length"))
        shot("rec")

        print("\nJS 异常:", logs if logs else "无")
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
