import subprocess
import time
import urllib.request
import json
import os
import sys

BROWSER = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 9334
UDD = os.path.join(os.environ["TEMP"], "edge_debug_udd_2")

proc = subprocess.Popen([
    BROWSER,
    "--headless=new",
    f"--remote-debugging-port={PORT}",
    f"--user-data-dir={UDD}",
    "http://127.0.0.1:8000/InkMentor.html"
])

try:
    tabs = []
    for _ in range(20):
        time.sleep(0.5)
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json") as r:
                tabs = json.loads(r.read().decode())
                if tabs:
                    break
        except Exception:
            pass

    target = None
    for t in tabs:
        if t.get("type") == "page" and "8000" in t.get("url", ""):
            target = t
            break

    if not target:
        print("No InkMentor page tab found!")
        sys.exit(1)

    import websockets
    import asyncio

    async def call_cdp(ws, msg_id, method, params=None):
        payload = {"id": msg_id, "method": method}
        if params:
            payload["params"] = params
        await ws.send(json.dumps(payload))
        while True:
            raw = await ws.recv()
            data = json.loads(raw)
            if data.get("id") == msg_id:
                return data

    async def main():
        ws_url = target["webSocketDebuggerUrl"]
        async with websockets.connect(ws_url) as ws:
            # Check TTS_MODE
            r1 = await call_cdp(ws, 1, "Runtime.evaluate", {"expression": "window.TTS_MODE"})
            print("window.TTS_MODE:", r1.get("result", {}).get("result", {}).get("value"))

            # Check /api/tts/status
            r2 = await call_cdp(ws, 2, "Runtime.evaluate", {
                "expression": "(async () => { const r = await fetch('/api/tts/status'); return await r.json(); })()",
                "awaitPromise": True,
                "returnByValue": True
            })
            print("API TTS Status:", r2.get("result", {}).get("result", {}).get("value"))

            # Test fetch('/api/tts') directly from browser page
            r3 = await call_cdp(ws, 3, "Runtime.evaluate", {
                "expression": """(async () => {
                    const r = await fetch('/api/tts', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({text: 'Let us solve this problem step by step.'})
                    });
                    const blob = await r.blob();
                    return { status: r.status, size: blob.size, type: blob.type };
                })()""",
                "awaitPromise": True,
                "returnByValue": True
            })
            print("Browser fetch /api/tts:", r3.get("result", {}).get("result", {}).get("value"))

            # Test audio element play from within browser page
            r4 = await call_cdp(ws, 4, "Runtime.evaluate", {
                "expression": """(async () => {
                    try {
                        const a = new Audio('data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA');
                        await a.play();
                        return { playSuccess: true };
                    } catch(e) {
                        return { playSuccess: false, error: e.name + ': ' + e.message };
                    }
                })()""",
                "awaitPromise": True,
                "returnByValue": True
            })
            print("Audio play test:", r4.get("result", {}).get("result", {}).get("value"))

    asyncio.run(main())
finally:
    proc.kill()
