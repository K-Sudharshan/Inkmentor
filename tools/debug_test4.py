import asyncio
import json
import websockets
import requests
import subprocess
import time
import os

EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 9256

async def send_cmd(ws, req_id, method, params=None):
    msg = {"id": req_id, "method": method}
    if params:
        msg["params"] = params
    await ws.send(json.dumps(msg))
    while True:
        resp = json.loads(await ws.recv())
        if resp.get("id") == req_id:
            return resp

async def evaluate(ws, req_id, expr, await_promise=False):
    params = {"expression": expr, "returnByValue": True, "awaitPromise": await_promise}
    res = await send_cmd(ws, req_id, "Runtime.evaluate", params)
    if "exceptionDetails" in res.get("result", {}):
        print("EXCEPTION in evaluate:", res["result"]["exceptionDetails"])
    val = res.get("result", {}).get("result", {}).get("value")
    if val is None:
        print("FULL RES:", res)
    return val

async def main():
    proc = subprocess.Popen([
        EDGE_EXE,
        f"--remote-debugging-port={PORT}",
        "--headless=new",
        "--autoplay-policy=no-user-gesture-required",
        "--user-data-dir=C:/Users/durga/AppData/Local/Temp/edge_debug_t4",
        "http://127.0.0.1:8000/InkMentor.html"
    ])
    try:
        await asyncio.sleep(2)
        tabs = requests.get(f"http://127.0.0.1:{PORT}/json").json()
        ws_url = None
        for t in tabs:
            if t.get("type") == "page" and "8000" in t.get("url", ""):
                ws_url = t.get("webSocketDebuggerUrl")
                break
        if not ws_url:
            ws_url = tabs[0]["webSocketDebuggerUrl"]

        async with websockets.connect(ws_url, max_size=50*1024*1024) as ws:
            req_id = 1
            await send_cmd(ws, req_id, "Runtime.enable")
            req_id += 1
            await send_cmd(ws, req_id, "Page.enable")
            req_id += 1

            # Wait for app readiness
            print("Waiting for page load and fonts...")
            for _ in range(40):
                ready = await evaluate(ws, req_id, "typeof window.ensureFontLoaded === 'function' && !!document.getElementById('notes')")
                req_id += 1
                if ready:
                    break
                await asyncio.sleep(0.2)

            # Enable console log collection
            await evaluate(ws, req_id, """
            window.debugLogs = [];
            var origLog = console.log;
            var origWarn = console.warn;
            var origErr = console.error;
            console.log = function() { window.debugLogs.push({type: 'log', args: Array.from(arguments).map(String)}); origLog.apply(console, arguments); };
            console.warn = function() { window.debugLogs.push({type: 'warn', args: Array.from(arguments).map(String)}); origWarn.apply(console, arguments); };
            console.error = function() { window.debugLogs.push({type: 'err', args: Array.from(arguments).map(String)}); origErr.apply(console, arguments); };
            """)
            req_id += 1

            # Run Test 4 directly
            print("Running Test 4 reproduction...")
            res = await evaluate(ws, req_id, """
            (async function() {
              window.TTS_MODE = 'cloud';
              window.go(8);

              var origFetch = window.fetch;
              window.fetch = async function(url, opts) {
                console.log('Fetch called:', url);
                if (typeof url === 'string' && url.indexOf('/api/tts') !== -1) {
                  console.log('Intercepted /api/tts, delaying 5s...');
                  await new Promise(function(r) { setTimeout(r, 5000); });
                  console.log('Returning 502 for /api/tts');
                  return new Response(JSON.stringify({ detail: 'Delayed' }), { status: 502 });
                }
                return origFetch.apply(this, arguments);
              };

              var errDetails = null;
              var t0 = performance.now();
              try {
                console.log('Calling runSolvePipeline...');
                await window.runSolvePipeline('Differentiate y = sin(3x^2)', null);
                console.log('runSolvePipeline completed');
              } catch (e) {
                console.error('runSolvePipeline caught error:', e);
                errDetails = { message: e.message, stack: e.stack };
              }
              var t1 = performance.now();
              window.fetch = origFetch;

              var steps = Array.from(document.querySelectorAll('.ln.ai[id^="step-"]'));
              return {
                stepCount: steps.length,
                completed: steps.length >= 3,
                busy: window.busy,
                elapsed: t1 - t0,
                err: errDetails,
                logs: window.debugLogs
              };
            })()
            """, await_promise=True)
            req_id += 1

            print("Test 4 Repro Result:")
            print(json.dumps(res, indent=2))
    finally:
        proc.kill()

if __name__ == "__main__":
    asyncio.run(main())
