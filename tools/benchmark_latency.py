import asyncio
import json
import os
import subprocess
import time
import urllib.request
import websockets

EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BROWSER_EXE = EDGE_EXE if os.path.exists(EDGE_EXE) else CHROME_EXE

async def cdp_call(ws, req_id, method, params=None):
    payload = {"id": req_id, "method": method}
    if params:
        payload["params"] = params
    await ws.send(json.dumps(payload))
    while True:
        resp = await ws.recv()
        data = json.loads(resp)
        if data.get("id") == req_id:
            return data

async def evaluate(ws, req_id, expression, await_promise=False):
    res = await cdp_call(ws, req_id, "Runtime.evaluate", {
        "expression": expression,
        "returnByValue": True,
        "awaitPromise": await_promise
    })
    result = res.get("result", {}).get("result", {})
    return result.get("value")

async def run_single_benchmark(question: str):
    temp_dir = os.path.join(os.environ.get("TEMP", "C:\\temp"), "inkmentor_perf_bench")
    os.makedirs(temp_dir, exist_ok=True)

    proc = subprocess.Popen([
        BROWSER_EXE,
        "--headless=new",
        "--remote-debugging-port=9223",
        f"--user-data-dir={temp_dir}",
        "--no-first-run",
        "--disable-gpu",
        "http://127.0.0.1:8000/"
    ])

    try:
        tab_ws_url = None
        for _ in range(25):
            await asyncio.sleep(0.4)
            try:
                with urllib.request.urlopen("http://127.0.0.1:9223/json", timeout=2) as r:
                    tabs = json.loads(r.read().decode())
                    for t in tabs:
                        if t.get("type") == "page" and "8000" in t.get("url", ""):
                            tab_ws_url = t.get("webSocketDebuggerUrl")
                            break
                    if tab_ws_url:
                        break
            except Exception:
                pass

        if not tab_ws_url:
            raise RuntimeError("Could not connect to browser via CDP.")

        async with websockets.connect(tab_ws_url, max_size=10*1024*1024) as ws:
            req_id = 1
            await cdp_call(ws, req_id, "Runtime.enable"); req_id += 1
            await cdp_call(ws, req_id, "Page.enable"); req_id += 1
            await asyncio.sleep(1.0)

            # Trigger a solve run directly
            js_code = f"""
            (async function() {{
                window.perfMarksReported = false;
                window.currentTraceId = 'trace_bench_' + Date.now();
                recordPerfMark('circle_finished');
                await new Promise(r => setTimeout(r, 10));
                recordPerfMark('crop_exported');
                await new Promise(r => setTimeout(r, 5));
                recordPerfMark('confirm_shown');
                await new Promise(r => setTimeout(r, 10));
                runSolvePipeline({json.dumps(question)}, {{x:100, y:100, w:300, h:150}});
                return true;
            }})()
            """
            await evaluate(ws, req_id, js_code, await_promise=True); req_id += 1

            # Poll for window.lastWaterfall
            waterfall = None
            for _ in range(60): # up to 30s
                await asyncio.sleep(0.5)
                res = await evaluate(ws, req_id, "window.lastWaterfall"); req_id += 1
                if res and res.get("table") and len(res.get("table")) > 0:
                    waterfall = res
                    break

            print("Captured Waterfall:", json.dumps(waterfall, indent=2))
            return waterfall
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            pass

if __name__ == "__main__":
    asyncio.run(run_single_benchmark("Differentiate y = sin(3x^2)"))
