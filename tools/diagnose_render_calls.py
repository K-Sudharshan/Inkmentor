import asyncio
import json
import os
import subprocess
import time
import urllib.request
import websockets

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 9240

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

async def evaluate(ws, req_id, expr, await_promise=False):
    res = await cdp_call(ws, req_id, "Runtime.evaluate", {
        "expression": expr,
        "returnByValue": True,
        "awaitPromise": await_promise
    })
    if "result" in res and "result" in res["result"]:
        if "value" in res["result"]["result"]:
            return res["result"]["result"]["value"]
        if "exceptionDetails" in res["result"]:
            print("EVAL ERROR:", res["result"]["exceptionDetails"])
            return None
    print("EVAL UNEXPECTED:", res)
    return None

async def main():
    temp_dir = os.path.join(os.environ.get("TEMP", "C:\\temp"), "inkmentor_diag_test")
    os.makedirs(temp_dir, exist_ok=True)
    browser_proc = subprocess.Popen([
        EDGE_PATH,
        f"--remote-debugging-port={PORT}",
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        f"--user-data-dir={temp_dir}",
        "http://localhost:8000/"
    ])
    try:
        tab_ws_url = None
        for _ in range(30):
            await asyncio.sleep(0.3)
            try:
                resp = urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json")
                pages = json.loads(resp.read().decode())
                for t in pages:
                    if t.get("type") == "page" and "8000" in t.get("url", ""):
                        tab_ws_url = t.get("webSocketDebuggerUrl")
                        break
                if tab_ws_url:
                    break
            except Exception:
                pass

        if not tab_ws_url:
            raise RuntimeError("Could not find 8000 page tab")

        async with websockets.connect(tab_ws_url, max_size=100_000_000) as ws:
            req_id = 1
            await cdp_call(ws, req_id, "Page.enable"); req_id += 1
            await cdp_call(ws, req_id, "Runtime.enable"); req_id += 1
            for _ in range(20):
                ready = await evaluate(ws, req_id, "!!document.getElementById('notes')")
                req_id += 1
                if ready:
                    break
                await asyncio.sleep(0.3)

            # Instrument render() and DOM modifications to trace who paints what and when
            instrument_script = """
            window.__traceLog = [];
            function logEvent(name, detail) {
                var entry = {
                    time: performance.now(),
                    name: name,
                    detail: detail,
                    stack: new Error().stack
                };
                window.__traceLog.push(entry);
                console.log('[TRACE]', name, detail);
            }

            var origRender = window.render;
            window.render = function(opt) {
                logEvent('render() called', { opt: opt, curPage: window.cur, hasAi: !!(window.pageAiOutput && window.pageAiOutput[window.cur]) });
                return origRender.apply(this, arguments);
            };

            var notes = document.getElementById('notes');
            var origAppendChild = notes.appendChild;
            notes.appendChild = function(child) {
                var desc = child.id || child.className || child.tagName;
                if (child.className && child.className.indexOf('ai') !== -1) {
                    desc += ' (text: ' + child.textContent.slice(0, 30) + ')';
                }
                logEvent('notes.appendChild', { desc: desc });
                return origAppendChild.apply(this, arguments);
            };

            var origEnsureFontLoaded = window.ensureFontLoaded;
            window.ensureFontLoaded = function() {
                logEvent('ensureFontLoaded() called', {});
                return origEnsureFontLoaded.apply(this, arguments);
            };
            """
            await evaluate(ws, req_id, instrument_script); req_id += 1

            # Switch to Page 8 and trigger Solve for "x^2 + 6x + 6"
            print("Triggering solve for x^2 + 6x + 6...")
            trigger_script = """
            (async function() {
                try {
                    window.go(8);
                    await window.ensureFontLoaded();
                    window.__traceLog = [];
                    console.log("Starting runSolvePipeline...");
                    var p = runSolvePipeline('x^2 + 6x + 6', null);
                    console.log("runSolvePipeline returned:", p);
                    return "started";
                } catch (e) {
                    console.error("Trigger error:", e);
                    return "error: " + e.message + " stack: " + e.stack;
                }
            })()
            """
            trig_res = await evaluate(ws, req_id, trigger_script, await_promise=True); req_id += 1
            print("Trigger result:", trig_res)

            # Poll traces every 500ms for 10 seconds
            for sec in range(20):
                await asyncio.sleep(0.5)
                traces = await evaluate(ws, req_id, "window.__traceLog.slice()"); req_id += 1
                dom_state = await evaluate(ws, req_id, """
                (function() {
                    var notes = document.getElementById('notes');
                    var children = Array.from(notes.children).map(function(c) {
                        var textEl = c.querySelector('.ai-reenie-line');
                        return {
                            id: c.id,
                            cls: c.className,
                            clip: textEl ? textEl.style.clipPath : 'N/A',
                            text: c.textContent.slice(0, 30)
                        };
                    });
                    return children;
                })()
                """); req_id += 1
                if dom_state is not None:
                    print(f"\n--- T = {sec*0.5:.1f}s | Notes Children: {len(dom_state)} ---")
                    for c in dom_state:
                        safe_text = c['text'].encode('ascii', 'replace').decode('ascii')
                        print(f"  {c['id']} ({c['cls']}): clip={c['clip']} | text={safe_text}")

                if traces:
                    for t in traces:
                        if t.get('reported'): continue
                        t['reported'] = True
                        print(f"  [EVENT at {t['time']:.1f}ms] {t['name']} : {t['detail']}")
                        # print stack if render
                        if 'render' in t['name']:
                            safe_stack = t['stack'].encode('ascii', 'replace').decode('ascii')
                            print("    STACK:", "\n    ".join(safe_stack.split("\n")[:5]))

                # If solve finished or has 4 steps, keep watching a bit
                if dom_state and len(dom_state) >= 5: # header, sp, 4 steps
                    pass
    finally:
        browser_proc.kill()

if __name__ == '__main__':
    asyncio.run(main())
