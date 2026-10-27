import asyncio
import json
import os
import subprocess
import time
import urllib.request
import websockets
import base64

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
    if "error" in res:
        print("EVAL ERROR:", res["error"])
        return None
    res_val = res.get("result", {})
    if "exceptionDetails" in res_val:
        print("EXCEPTION DETAILS:", res_val["exceptionDetails"])
        return None
    return res_val.get("result", {}).get("value")

async def verify_math_symbols():
    temp_dir = os.path.join(os.environ.get("TEMP", "C:\\temp"), f"ink_math_{int(time.time())}")
    os.makedirs(temp_dir, exist_ok=True)

    print(f"Starting browser verification using: {BROWSER_EXE}")
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
            time.sleep(0.4)
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
            print("ERROR: Could not attach to browser page via CDP.")
            return False

        async with websockets.connect(tab_ws_url, max_size=100_000_000) as ws:
            req_id = 1
            await asyncio.sleep(1.5)
            await evaluate(ws, req_id, "window.TEST_MODE = true;")
            req_id += 1

            # Wait for app ready
            await evaluate(ws, req_id, """
            new Promise(function(resolve) {
                if (document.readyState === 'complete') resolve();
                else window.addEventListener('load', resolve);
            })
            """, await_promise=True)
            req_id += 1

            # Test formatting of the user's exact lines
            test_res = await evaluate(ws, req_id, """
            (function() {
                var ls = document.getElementById('loader-screen');
                if (ls) ls.remove();
                var lines = [
                    'int_0^1 x^2 [y^2 / 2]_0^2 dx',
                    'int_0^1 x^2 (4 / 2 - 0) dx',
                    '[2 * x^3 / 3]_0^1',
                    '2(1)^3 / 3 - 0 = 2/3'
                ];
                var testDiv = document.createElement('div');
                testDiv.id = 'math-test-container';
                testDiv.style.position = 'absolute';
                testDiv.style.top = '100px';
                testDiv.style.left = '320px';
                testDiv.style.zIndex = '9999';
                testDiv.style.background = 'rgba(255,255,255,0.95)';
                testDiv.style.padding = '20px';
                testDiv.style.borderRadius = '16px';
                document.body.appendChild(testDiv);

                var results = [];
                lines.forEach(function(l) {
                    var lineObj = window.buildLineSvg(l);
                    testDiv.appendChild(lineObj.el);

                    // Check elements in lineObj
                    var intWrap = lineObj.el.querySelectorAll('.math-integral-wrap');
                    var evalBrackets = lineObj.el.querySelectorAll('.math-eval-bracket');
                    var svgs = lineObj.el.querySelectorAll('.math-svg');
                    var cdots = lineObj.el.querySelectorAll('.math-cdot');
                    var sups = lineObj.el.querySelectorAll('.math-sup');
                    var diffs = lineObj.el.querySelectorAll('.math-diff');

                    results.push({
                        line: l,
                        intWrapCount: intWrap.length,
                        evalBracketCount: evalBrackets.length,
                        svgCount: svgs.length,
                        cdotCount: cdots.length,
                        supCount: sups.length,
                        diffCount: diffs.length
                    });
                });
                return { results: results, html: testDiv.innerHTML };
            })()
            """)
            req_id += 1

            print("\nVerification Results:")
            for r in test_res["results"]:
                print(r)

            # Assertions
            line0 = test_res["results"][0]
            assert line0["intWrapCount"] == 2, f"Expected 2 math wraps in line 0, got {line0['intWrapCount']}"
            assert line0["evalBracketCount"] == 1, f"Expected 1 eval bracket in line 0, got {line0['evalBracketCount']}"
            assert line0["diffCount"] == 1, f"Expected 1 diff in line 0, got {line0['diffCount']}"

            line1 = test_res["results"][1]
            assert line1["intWrapCount"] == 1, f"Expected 1 integral wrap in line 1, got {line1['intWrapCount']}"
            assert line1["diffCount"] == 1, f"Expected 1 diff in line 1, got {line1['diffCount']}"

            line2 = test_res["results"][2]
            assert line2["evalBracketCount"] == 1, f"Expected 1 eval bracket in line 2, got {line2['evalBracketCount']}"
            assert line2["cdotCount"] == 1, f"Expected 1 cdot in line 2, got {line2['cdotCount']}"

            # Capture screenshot
            ss = await cdp_call(ws, req_id, "Page.captureScreenshot")
            req_id += 1
            img_data = ss.get("result", {}).get("data")
            if img_data:
                with open("math_symbols_verified.png", "wb") as f:
                    f.write(base64.b64decode(img_data))
                print("\nCaptured math_symbols_verified.png successfully!")

            print("\nALL MATH SYMBOL ASSERTIONS PASSED! Real symbols are active.")
            return True

    finally:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            pass

if __name__ == "__main__":
    success = asyncio.run(verify_math_symbols())
    exit(0 if success else 1)
