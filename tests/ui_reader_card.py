"""阅读页专项真机验收：正文 [n] 跳参考文献 → 返回正文；中英对照开关与滚动联动。
用法：python tests/ui_reader_card.py
"""
import base64
import json
import subprocess
import time
from pathlib import Path

import httpx

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
OUT = Path(r"E:\项目\科研小助手\data")
PORT = 9226


def boot():
    proc = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", f"--remote-debugging-port={PORT}",
                             "--user-data-dir=" + str(OUT / "edge_prof3"), "--window-size=1600,1100",
                             "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import websocket
    target = None
    for _ in range(40):
        try:
            t = [x for x in httpx.get(f"http://127.0.0.1:{PORT}/json", timeout=2).json() if x["type"] == "page"]
            if t:
                target = t
                break
        except Exception:
            time.sleep(0.5)
    ws = websocket.create_connection(target[0]["webSocketDebuggerUrl"], timeout=60)
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
        res = r.get("result", {}).get("result", {})
        if r.get("result", {}).get("exceptionDetails"):
            return "ERR " + str(r["result"]["exceptionDetails"].get("text"))
        return res.get("value")

    def shot(name):
        r = send("Page.captureScreenshot", {"format": "png"})
        (OUT / f"reader_{name}.png").write_bytes(base64.b64decode(r["result"]["data"]))
        print(f"  截图 reader_{name}.png")

    send("Runtime.enable")
    send("Page.enable")
    send("Page.navigate", {"url": "http://127.0.0.1:8000"})
    time.sleep(4)
    return proc, js, shot, logs


def main():
    proc, js, shot, logs = boot()
    try:
        print("1) 进入阅读页，选中 Attention")
        js("document.querySelector('.tabs button[data-tab=\"reader\"]').click()")
        time.sleep(2)
        ok = js("(()=>{const s=document.querySelector('#readerPaper');"
               "if(!s.options.length) return 'no options';"
               "const pick=[...s.options].find(o=>o.value==='1');"
               "const i=[...s.options].indexOf(pick || [...s.options].find(o=>/Attention/.test(o.textContent)));"
               "s.selectedIndex=i<0?0:i; s.dispatchEvent(new Event('change')); return s.value;})()")
        print("   选中 pid:", ok)
        time.sleep(4)
        print("   参考文献条数:", js("document.querySelectorAll('#refList .ref-item').length"))
        js("(()=>{document.querySelector('#btnNextPage').click();})()")
        time.sleep(3)
        cites = js("document.querySelectorAll('#pageWrap .cit').length")
        print("   第2页正文引用标记数:", cites)
        shot("page2")

        print("2) 点正文 [1] 跳参考文献")
        js("(()=>{const c=document.querySelector('#pageWrap .cit'); c.click(); return 1;})()")
        time.sleep(2)
        print("   高亮条目:", js("document.querySelector('#refList .ref-item.active')?.textContent.slice(0,60)"))
        print("   返回按钮可见:", js("!document.querySelector('#btnBackFromRef').hidden"))
        shot("refjump")

        print("3) 点返回正文")
        js("document.querySelector('#btnBackFromRef').click()")
        time.sleep(2)
        print("   回到页:", js("document.querySelector('#pageIndicator').textContent"),
              "| 滚动位置:", js("document.querySelector('#pagePane').scrollTop"))
        print("   返回按钮已隐藏:", js("document.querySelector('#btnBackFromRef').hidden"))

        print("4) 开中英对照")
        js("(()=>{const c=document.querySelector('#chkCompare'); c.checked=true; c.dispatchEvent(new Event('change')); return 1;})()")
        time.sleep(10)
        print("   body 类:", js("document.body.className"))
        print("   译文条数:", js("document.querySelectorAll('#transList .item').length"))
        js("document.querySelector('#pagePane').scrollTop = 400")
        time.sleep(1)
        print("   联动后右栏 scrollTop:", js("document.querySelector('#transPane').scrollTop"))
        print("   右栏可滚动高度:", js("(()=>{const t=document.querySelector('#transPane');return t.scrollHeight+'/'+t.clientHeight})()"),
              "左栏:", js("(()=>{const t=document.querySelector('#pagePane');return t.scrollHeight+'/'+t.clientHeight})()"))
        shot("compare")

        print("\nJS 异常:", logs if logs else "无")
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
