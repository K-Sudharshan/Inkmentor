import os
import sys
import json
import time
import subprocess
import urllib.request
import asyncio
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
    if "error" in res:
        print("EVAL ERROR:", res["error"])
        return None
    res_val = res.get("result", {})
    if "exceptionDetails" in res_val:
        print("EXCEPTION DETAILS:", res_val["exceptionDetails"])
        return None
    return res_val.get("result", {}).get("value")

async def run_checks():
    temp_dir = os.path.join(os.environ.get("TEMP", "C:\\temp"), "inkmentor_overlap_check")
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

            print("\n--- TEST 1: Question Header (#ai-question) is Hidden from View ---")
            check_q = await evaluate(ws, req_id, """
            (function() {
                var notes = document.getElementById('notes');
                // Simulate setting an AI output with question
                window.pageAiOutput[8] = {
                    question: 'Evaluate double integral of x*y over [0,1]x[0,2]',
                    steps: [{ write: 'int(0,2) [x^2*y/2] dy', narration: 'Integrate with respect to x first.' }],
                    box: { x: 50, y: 80, w: 300, h: 70 }
                };
                window.go(8);
                var qEl = document.getElementById('ai-question');
                var isHidden = !qEl || window.getComputedStyle(qEl).display === 'none';
                var qRect = qEl ? qEl.getBoundingClientRect() : null;
                return {
                    qExistsInDom: !!qEl,
                    isHidden: isHidden,
                    qHeight: qRect ? qRect.height : 0
                };
            })()
            """)
            req_id += 1
            print("Test 1 Result:", check_q)
            assert check_q["qExistsInDom"] is True, "ai-question should exist in DOM for tests"
            assert check_q["isHidden"] is True, "ai-question must be display: none"
            assert check_q["qHeight"] == 0, "ai-question must occupy 0 height"
            print(">>> PASS: #ai-question is hidden from visible view, occupying 0 height.")

            print("\n--- TEST 2: Answer Does NOT Overlap User's Circled Question ---")
            check_overlap = await evaluate(ws, req_id, """
            (function() {
                // User handwritten question bounding box: y=120, h=90 -> bottom is 210
                var questionBox = { x: 60, y: 120, w: 320, h: 90 };
                var questionBottom = questionBox.y + questionBox.h; // 210

                window.pageAiOutput[9] = {
                    question: 'int_0^1 int_0^2 x*y dy dx',
                    steps: [
                        { write: 'int_0^1 [x*y^2/2]_0^2 dx', narration: 'First integrate with respect to y.' },
                        { write: 'int_0^1 2x dx = [x^2]_0^1', narration: 'Now integrate the remaining x term.' },
                        { write: '1', narration: 'Evaluating at the limits gives one.' }
                    ],
                    box: questionBox
                };
                window.go(9);

                var notes = document.getElementById('notes');
                var notesPadTop = parseFloat(window.getComputedStyle(notes).paddingTop);
                var step0 = document.getElementById('step-0');
                var step0Rect = step0.getBoundingClientRect();
                var paperRect = document.getElementById('paper').getBoundingClientRect();
                var step0YInPaper = step0Rect.top - paperRect.top;

                return {
                    questionBottom: questionBottom,
                    notesPadTop: notesPadTop,
                    step0YInPaper: step0YInPaper,
                    isBelowQuestion: step0YInPaper >= questionBottom,
                    clearancePx: step0YInPaper - questionBottom
                };
            })()
            """)
            req_id += 1
            print("Test 2 Result:", check_overlap)
            assert check_overlap["isBelowQuestion"] is True, "Step 0 must be positioned below questionBottom"
            assert check_overlap["clearancePx"] >= 10, "There must be comfortable clearance between question and answer"
            print(f">>> PASS: Answer begins at Y={check_overlap['step0YInPaper']}px, with {check_overlap['clearancePx']}px clearance below question bottom ({check_overlap['questionBottom']}px). NO overlap!")

            print("\n--- TEST 3: Clearing Solution Resets Top Padding ---")
            check_clear = await evaluate(ws, req_id, """
            (function() {
                var notes = document.getElementById('notes');
                var origConfirm = window.confirm;
                window.confirm = function() { return true; };
                var clearBtn = document.getElementById('clear-sol-btn');
                if (clearBtn) clearBtn.click();
                window.confirm = origConfirm;

                var afterPadTop = notes.style.paddingTop;
                return {
                    clearedPadTop: afterPadTop,
                    hasAiOutput: !!window.pageAiOutput[9]
                };
            })()
            """)
            req_id += 1
            print("Test 3 Result:", check_clear)
            assert check_clear["hasAiOutput"] is False, "pageAiOutput should be removed"
            assert check_clear["clearedPadTop"] == "", "notes.style.paddingTop should be reset to empty"
            print(">>> PASS: Solution cleared and paddingTop cleanly reset.")

            print("\n--- TEST 4: Live runSolvePipeline with Circled Box Positions Below Question ---")
            check_live = await evaluate(ws, req_id, """
            (async function() {
                var qBox = { x: 80, y: 150, w: 280, h: 80 }; // bottom is 230
                var p = window.runSolvePipeline('int x^2 dx', qBox);
                var notes = document.getElementById('notes');
                var ind = document.getElementById('ai-solving-indicator');
                var indRect = ind ? ind.getBoundingClientRect() : null;
                var paperRect = document.getElementById('paper').getBoundingClientRect();
                var indY = indRect ? (indRect.top - paperRect.top) : 0;

                return {
                    qBottom: qBox.y + qBox.h,
                    solvingIndY: indY,
                    indBelowQ: indY >= (qBox.y + qBox.h),
                    notesPad: parseFloat(notes.style.paddingTop || 0)
                };
            })()
            """, await_promise=True)
            req_id += 1
            print("Test 4 Result:", check_live)
            assert check_live["indBelowQ"] is True, "Solving indicator must appear below question"
            print(">>> PASS: Live solve pipeline immediately positions content below the circled question.")

            print("\nALL 4 BROWSER CHECKS PASSED SUCCESSFULLY!")
            return True

    finally:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

if __name__ == "__main__":
    success = asyncio.run(run_checks())
    sys.exit(0 if success else 1)
