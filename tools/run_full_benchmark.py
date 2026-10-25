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

PROBLEMS = [
    "Differentiate y = sin(3x^2)",
    "Integrate x^2 * exp(x)",
    "Solve x^2 - 5x + 6 = 0",
    "Differentiate y = (x^2 + 1)^3",
    "Integrate 2*x / (x^2 + 1)"
]

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

async def run_suite():
    temp_dir = os.path.join(os.environ.get("TEMP", "C:\\temp"), "inkmentor_perf_suite")
    os.makedirs(temp_dir, exist_ok=True)

    proc = subprocess.Popen([
        BROWSER_EXE,
        "--headless=new",
        "--remote-debugging-port=9224",
        f"--user-data-dir={temp_dir}",
        "--no-first-run",
        "--disable-gpu",
        "http://127.0.0.1:8000/"
    ])

    results = []

    try:
        tab_ws_url = None
        for _ in range(25):
            await asyncio.sleep(0.4)
            try:
                with urllib.request.urlopen("http://127.0.0.1:9224/json", timeout=2) as r:
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

            for prob_idx, question in enumerate(PROBLEMS, 1):
                for run_idx in range(1, 4):
                    trace_prefix = f"trace_p{prob_idx}_r{run_idx}_"
                    print(f"[{prob_idx}/5] Problem: '{question}' | Run {run_idx}/3...", flush=True)
                    await cdp_call(ws, req_id, "Page.reload"); req_id += 1
                    await asyncio.sleep(1.2)

                    js_code = f"""
                    (async function() {{
                        window.perfMarksReported = false;
                        window.currentTraceId = '{trace_prefix}' + Date.now();
                        recordPerfMark('circle_finished');
                        await new Promise(r => setTimeout(r, 12));
                        recordPerfMark('crop_exported');
                        await new Promise(r => setTimeout(r, 8));
                        recordPerfMark('confirm_shown');
                        await new Promise(r => setTimeout(r, 15));
                        runSolvePipeline({json.dumps(question)}, {{x:100, y:100, w:300, h:150}});
                        return true;
                    }})()
                    """
                    await evaluate(ws, req_id, js_code, await_promise=True); req_id += 1

                    waterfall = None
                    for _ in range(60):
                        await asyncio.sleep(0.5)
                        wf = await evaluate(ws, req_id, "window.lastWaterfall"); req_id += 1
                        if wf and wf.get("table") and len(wf.get("table")) > 0:
                            waterfall = wf
                            break

                    if waterfall:
                        m = waterfall["marks"]
                        solve_to_stroke = (m.get("first_stroke_painted") or m.get("first_step_visible", 0)) - m.get("solve_clicked", 0)
                        circle_to_stroke = (m.get("first_stroke_painted") or m.get("first_step_visible", 0)) - m.get("circle_finished", 0)
                        entry = {
                            "problem": question,
                            "run": run_idx,
                            "trace_id": waterfall.get("trace_id"),
                            "solve_to_stroke_ms": round(solve_to_stroke, 1),
                            "circle_to_stroke_ms": round(circle_to_stroke, 1),
                            "marks": m,
                            "table": waterfall.get("table", []),
                            "server": waterfall.get("server", {})
                        }
                        results.append(entry)
                        print(f" -> Solve-to-stroke: {solve_to_stroke:.1f}ms | Circle-to-stroke: {circle_to_stroke:.1f}ms")
                    else:
                        print(" -> Timeout waiting for waterfall!")

                    # Brief settle pause between runs
                    await asyncio.sleep(1.0)

            with open("tools/out_baseline_measurements.json", "w") as f:
                json.dump(results, f, indent=2)

            print("\nSaved 15 baseline runs to tools/out_baseline_measurements.json")
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            pass

if __name__ == "__main__":
    asyncio.run(run_suite())
