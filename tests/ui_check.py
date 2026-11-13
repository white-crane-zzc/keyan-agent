"""用 CDP 驱动无头 Edge 逐个页签渲染并截图，同时收集控制台报错。
用法：python tests/ui_check.py
"""
import json
import subprocess
import time
from pathlib import Path

import httpx

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
OUT = Path(r"E:\项目\科研小助手\data")
PORT = 9223

TABS = ["library", "reader", "qa", "graph", "write", "rec"]


def cdp_targets():
    for _ in range(30):
        try:
            return httpx.get(f"http://127.0.0.1:{PORT}/json", timeout=2).json()
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("CDP 未就绪")


def main():
    proc = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", f"--remote-debugging-port={PORT}",
                             "--user-data-dir=" + str(OUT / "edge_prof"), "--window-size=1600,1100",
                             "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        import websocket
        targets = [t for t in cdp_targets() if t["type"] == "page"]
        ws_url = targets[0]["webSocketDebuggerUrl"]
        ws = websocket.create_connection(ws_url, timeout=30)
        mid = [0]
        logs = []

        def send(method, params=None):
            mid[0] += 1
            ws.send(json.dumps({"id": mid[0], "method": method, "params": params or {}}))
            while True:
                msg = json.loads(ws.recv())
                if msg.get("id") == mid[0]:
                    return msg
                ev = msg.get("method")
                if ev == "Runtime.exceptionThrown":
                    logs.append(("EXC", str(msg["params"])[:300]))
                elif ev == "Log.entryAdded" and msg["params"]["entry"]["level"] in ("error", "warning"):
                    logs.append((msg["params"]["entry"]["level"], msg["params"]["entry"]["text"][:300]))

        send("Runtime.enable")
        send("Log.enable")
        send("Page.enable")
        send("Page.navigate", {"url": "http://127.0.0.1:8000"})
        time.sleep(4)

        for tab in TABS:
            send("Runtime.evaluate", {"expression":
                f"document.querySelector('.tabs button[data-tab=\"{tab}\"]').click()"})
            time.sleep(3.5)
            shot = send("Page.captureScreenshot", {"format": "png"})
            data = shot["result"]["data"]
            import base64
            (OUT / f"shot_{tab}.png").write_bytes(base64.b64decode(data))
            print(f"截图 {tab}: {(OUT / f'shot_{tab}.png').stat().st_size} 字节")

        print("\n控制台异常/报错:")
        if not logs:
            print("  无")
        for l in logs[:30]:
            print(" ", l)
        ws.close()
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
