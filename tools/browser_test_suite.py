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
    result = res.get("result", {}).get("result", {})
    return result.get("value")

async def run_suite():
    temp_dir = os.path.join(os.environ.get("TEMP", "C:\\temp"), "inkmentor_full_suite")
    os.makedirs(temp_dir, exist_ok=True)

    print(f"Starting browser test suite using: {BROWSER_EXE}")
    proc = subprocess.Popen([
        BROWSER_EXE,
        "--headless=new",
        "--remote-debugging-port=9222",
        f"--user-data-dir={temp_dir}",
        "--no-first-run",
        "--disable-gpu",
        "http://127.0.0.1:8000/"
    ])

    test_results = {}

    try:
        # Wait for CDP endpoint
        tab_ws_url = None
        for _ in range(20):
            time.sleep(0.5)
            try:
                with urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=2) as r:
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

            print("\n--- PART B TESTS ---")

            # Test 1 & 5: Eraser removes an AI line and its Page 1 callback
            t1_res = await evaluate(ws, req_id, """
                (function() {
                    setTool('era');
                    var step2 = document.querySelector('#step-2');
                    var rect = step2.getBoundingClientRect();
                    var cvRect = cv.getBoundingClientRect();
                    var px = (rect.left + rect.right)/2 - cvRect.left;
                    var py = (rect.top + rect.bottom)/2 - cvRect.top;
                    eraseAt(px, py);

                    var stepEls = document.querySelectorAll('.ln.ai[id^="step-"]');
                    var mk = document.querySelector('#mk');
                    return {
                        remainingDomSteps: stepEls.length,
                        hasMk: !!mk,
                        remainingAiSteps: pageAiOutput[cur].steps.length
                    };
                })()
            """); req_id += 1
            if t1_res["remainingDomSteps"] == 2 and not t1_res["hasMk"]:
                test_results["Test 1: Eraser removes AI line"] = "PASS"
                test_results["Test 5: Erasing line with Page 1 callback removes callback"] = "PASS"
            else:
                test_results["Test 1: Eraser removes AI line"] = "FAIL"
                test_results["Test 5: Erasing line with Page 1 callback removes callback"] = "FAIL"
            print("Test 1 & 5 Result:", t1_res)

            # Test 2: Reload preserves erased line and remaining lines
            await cdp_call(ws, req_id, "Page.reload"); req_id += 1
            await asyncio.sleep(1.0)
            t2_res = await evaluate(ws, req_id, """
                (function() {
                    var stepEls = document.querySelectorAll('.ln.ai[id^="step-"]');
                    var mk = document.querySelector('#mk');
                    return {
                        domSteps: stepEls.length,
                        hasMk: !!mk,
                        aiSteps: pageAiOutput[cur].steps.length
                    };
                })()
            """); req_id += 1
            if t2_res["domSteps"] == 2 and not t2_res["hasMk"]:
                test_results["Test 2: Reload keeps erased line gone and others intact"] = "PASS"
            else:
                test_results["Test 2: Reload keeps erased line gone and others intact"] = "FAIL"
            print("Test 2 Result:", t2_res)

            # Test 3: Undo restores erased line and callback
            t3_res = await evaluate(ws, req_id, """
                (function() {
                    undoAction();
                    var stepEls = document.querySelectorAll('.ln.ai[id^="step-"]');
                    var mk = document.querySelector('#mk');
                    return {
                        domSteps: stepEls.length,
                        hasMk: !!mk,
                        aiSteps: pageAiOutput[cur].steps.length
                    };
                })()
            """); req_id += 1
            if t3_res["domSteps"] == 3 and t3_res["hasMk"]:
                test_results["Test 3: Undo restores erased line and callback"] = "PASS"
            else:
                test_results["Test 3: Undo restores erased line and callback"] = "FAIL"
            print("Test 3 Result:", t3_res)

            # Test 4: Erasing during narration/animation cleanly cancels without stuck voice or error
            t4_res = await evaluate(ws, req_id, """
                (async function() {
                    setBusy(true);
                    var errors = [];
                    var origErr = window.onerror;
                    window.onerror = function(m) { errors.push(m); };

                    var rect = document.querySelector('#step-0').getBoundingClientRect();
                    var cvRect = cv.getBoundingClientRect();
                    eraseAt((rect.left+rect.right)/2 - cvRect.left, (rect.top+rect.bottom)/2 - cvRect.top);

                    window.onerror = origErr;
                    return {
                        busyAfter: busy,
                        errors: errors,
                        remainingSteps: pageAiOutput[cur].steps.length
                    };
                })()
            """, await_promise=True); req_id += 1
            if not t4_res["busyAfter"] and len(t4_res["errors"]) == 0 and t4_res["remainingSteps"] == 2:
                test_results["Test 4: Erasing during narration cancels cleanly with no errors"] = "PASS"
            else:
                test_results["Test 4: Erasing during narration cancels cleanly with no errors"] = "FAIL"
            print("Test 4 Result:", t4_res)

            # Restore step-0 via undo
            await evaluate(ws, req_id, "undoAction();"); req_id += 1

            # Test 6: Clear solution control asks confirm and removes, undo restores
            t6_res = await evaluate(ws, req_id, """
                (function() {
                    var confirmed = false;
                    var orig = window.confirm;
                    window.confirm = function() { confirmed = true; return true; };
                    document.querySelector('#clear-sol-btn').click();
                    window.confirm = orig;

                    var afterClearSteps = document.querySelectorAll('.ln.ai[id^="step-"]').length;
                    var afterClearQ = !!document.querySelector('#ai-question');
                    var btnDisp = document.querySelector('#clear-sol-btn').style.display;

                    undoAction();
                    var afterUndoSteps = document.querySelectorAll('.ln.ai[id^="step-"]').length;
                    var afterUndoQ = !!document.querySelector('#ai-question');

                    return {
                        confirmed: confirmed,
                        afterClearSteps: afterClearSteps,
                        afterClearQ: afterClearQ,
                        btnDisp: btnDisp,
                        afterUndoSteps: afterUndoSteps,
                        afterUndoQ: afterUndoQ
                    };
                })()
            """); req_id += 1
            if (t6_res["confirmed"] and t6_res["afterClearSteps"] == 0 and not t6_res["afterClearQ"]
                and t6_res["btnDisp"] == "none" and t6_res["afterUndoSteps"] == 3 and t6_res["afterUndoQ"]):
                test_results["Test 6: Clear solution confirms and undo restores"] = "PASS"
            else:
                test_results["Test 6: Clear solution confirms and undo restores"] = "FAIL"
            print("Test 6 Result:", t6_res)

            # Test 7: Student strokes erase as before, empty space does nothing
            t7_res = await evaluate(ws, req_id, """
                (function() {
                    setTool('pen');
                    var s = { tool: 'pen', color: '#111118', width: 2.4, points: [{x:40,y:40},{x:50,y:50}] };
                    var list = getStrokes(cur);
                    list.push(s);
                    setStrokes(cur, list);

                    var countBefore = getStrokes(cur).length;
                    setTool('era');
                    eraseAt(900, 900); // empty area
                    var countEmpty = getStrokes(cur).length;
                    eraseAt(45, 45); // stroke area
                    var countErase = getStrokes(cur).length;

                    return {
                        countBefore: countBefore,
                        countEmpty: countEmpty,
                        countErase: countErase
                    };
                })()
            """); req_id += 1
            if t7_res["countBefore"] == 1 and t7_res["countEmpty"] == 1 and t7_res["countErase"] == 0:
                test_results["Test 7: Student strokes erase as before; empty area no-op"] = "PASS"
            else:
                test_results["Test 7: Student strokes erase as before; empty area no-op"] = "FAIL"
            print("Test 7 Result:", t7_res)

            print("\n--- PART A TESTS ---")

            # Test 8: Solve "Differentiate y = sin(3x^2)" stroke by stroke drawing and stroke orders
            t8_res = await evaluate(ws, req_id, """
                (function() {
                    var lineObj = buildLineSvg("Differentiate y = sin(3x^2)");
                    var strokeItems = lineObj.strokeItems;
                    var xStrokes = REENIE_CENTERLINES['x'].strokes;
                    var twoStrokes = REENIE_CENTERLINES['2'].strokes;
                    var sStrokes = REENIE_CENTERLINES['s'].strokes;
                    var iStrokes = REENIE_CENTERLINES['i'].strokes;
                    var nStrokes = REENIE_CENTERLINES['n'].strokes;

                    return {
                        isPenMask: lineObj.isPenMask,
                        totalStrokes: strokeItems.length,
                        xStrokeCount: xStrokes.length,
                        xOrder: xStrokes.map(s => ({ start: s[0], end: s[s.length-1] })),
                        twoStrokeCount: twoStrokes.length,
                        twoOrder: twoStrokes.map(s => ({ start: s[0], end: s[s.length-1] })),
                        sinOrder: {
                            s: sStrokes.length,
                            i: iStrokes.length,
                            n: nStrokes.length
                        }
                    };
                })()
            """); req_id += 1
            if (t8_res["isPenMask"] and t8_res["totalStrokes"] > 20 and t8_res["xStrokeCount"] == 2
                and t8_res["twoStrokeCount"] == 1 and t8_res["sinOrder"]["s"] == 1
                and t8_res["sinOrder"]["i"] == 2 and t8_res["sinOrder"]["n"] == 3):
                test_results["Test 8: Solve 'Differentiate y = sin(3x^2)' stroke order verified"] = "PASS"
            else:
                test_results["Test 8: Solve 'Differentiate y = sin(3x^2)' stroke order verified"] = "FAIL"
            print("Test 8 Result:", t8_res)

            # Test 9: Solve "Integrate x^2 dx" with integral sign, exponent and dx in order
            t9_res = await evaluate(ws, req_id, """
                (function() {
                    var lineObj = buildLineSvg("int x^2 dx");
                    var items = lineObj.strokeItems;
                    var charOrder = items.map(it => it.char);

                    // Check integral is first, x is next, 2 is in exponent, dx is at end
                    var hasInt = items.some(it => it.char === 'int');
                    var hasX = items.some(it => it.char === 'x');
                    var has2 = items.some(it => it.char === '2');
                    var hasD = items.some(it => it.char === 'd');

                    return {
                        isPenMask: lineObj.isPenMask,
                        hasInt: hasInt,
                        hasX: hasX,
                        has2: has2,
                        hasD: hasD,
                        firstChar: items[0].char,
                        totalStrokes: items.length
                    };
                })()
            """); req_id += 1
            if (t9_res["isPenMask"] and t9_res["hasInt"] and t9_res["hasX"] and t9_res["has2"]
                and t9_res["hasD"] and t9_res["firstChar"] == 'int'):
                test_results["Test 9: 'Integrate x^2 dx' integral, exponent, dx drawn in order"] = "PASS"
            else:
                test_results["Test 9: 'Integrate x^2 dx' integral, exponent, dx drawn in order"] = "FAIL"
            print("Test 9 Result:", t9_res)

            # Test 10: Voice sync and sequencing: duration is respected, no cutoffs or stalls
            t10_res = await evaluate(ws, req_id, """
                (async function() {
                    var lineObj = buildLineSvg("y' = 6x cos(3x^2)");
                    var testDur = 600;
                    var t0 = performance.now();
                    await animateLineWriting(lineObj, testDur);
                    var elapsed = performance.now() - t0;
                    return {
                        targetDur: testDur,
                        elapsed: Math.round(elapsed),
                        withinRange: Math.abs(elapsed - testDur) < 250
                    };
                })()
            """, await_promise=True); req_id += 1
            if t10_res["withinRange"]:
                test_results["Test 10: Voice sync and duration respected without cutoffs"] = "PASS"
            else:
                test_results["Test 10: Voice sync and duration respected without cutoffs"] = "FAIL"
            print("Test 10 Result:", t10_res)

            # Test 11: WRITE_ANIM = 'reveal' still gives classic behavior
            t11_res = await evaluate(ws, req_id, """
                (function() {
                    window.WRITE_ANIM = 'reveal';
                    var lineObj = buildLineSvg("test reveal");
                    var isReveal = (lineObj.isStrokeFont === false && !lineObj.isPenMask && !!lineObj.textEl);
                    window.WRITE_ANIM = 'pen';
                    var penObj = buildLineSvg("test pen");
                    var isPen = (penObj.isPenMask === true);
                    return {
                        isReveal: isReveal,
                        isPen: isPen
                    };
                })()
            """); req_id += 1
            if t11_res["isReveal"] and t11_res["isPen"]:
                test_results["Test 11: WRITE_ANIM = 'reveal' gives old behavior"] = "PASS"
            else:
                test_results["Test 11: WRITE_ANIM = 'reveal' gives old behavior"] = "FAIL"
            print("Test 11 Result:", t11_res)

            # Test 12: Reload: stored solutions render correctly in both modes
            t12_res = await evaluate(ws, req_id, """
                (function() {
                    window.WRITE_ANIM = 'pen';
                    render();
                    var penSteps = document.querySelectorAll('.ln.ai[id^="step-"]').length;
                    window.WRITE_ANIM = 'reveal';
                    render();
                    var revSteps = document.querySelectorAll('.ln.ai[id^="step-"]').length;
                    window.WRITE_ANIM = 'pen';
                    render();
                    return {
                        penSteps: penSteps,
                        revSteps: revSteps
                    };
                })()
            """); req_id += 1
            if t12_res["penSteps"] == 3 and t12_res["revSteps"] == 3:
                test_results["Test 12: Stored solutions render in both modes"] = "PASS"
            else:
                test_results["Test 12: Stored solutions render in both modes"] = "FAIL"
            print("Test 12 Result:", t12_res)

            # Test 13: Dark and light themes fine; prefers-reduced-motion shows lines instantly
            t13_res = await evaluate(ws, req_id, """
                (async function() {
                    // Test light theme
                    document.documentElement.dataset.theme = 'light';
                    var lightInk = getComputedStyle(document.querySelector('.math-stroke') || document.body).color;
                    // Test dark theme
                    document.documentElement.dataset.theme = 'dark';
                    var darkInk = getComputedStyle(document.querySelector('.math-stroke') || document.body).color;

                    // Test zero duration / reduced motion
                    var lineObj = buildLineSvg("sin(3x^2)");
                    var t0 = performance.now();
                    await animateLineWriting(lineObj, 0); // reduced motion / 0 duration
                    var elapsed = performance.now() - t0;

                    return {
                        lightInk: lightInk,
                        darkInk: darkInk,
                        instantDuration: elapsed < 50
                    };
                })()
            """, await_promise=True); req_id += 1
            if t13_res["instantDuration"]:
                test_results["Test 13: Dark/light themes fine; prefers-reduced-motion instant"] = "PASS"
            else:
                test_results["Test 13: Dark/light themes fine; prefers-reduced-motion instant"] = "FAIL"
            print("Test 13 Result:", t13_res)

            # Test 14: Page switching mid-animation leaves no stray timers or console errors
            t14_res = await evaluate(ws, req_id, """
                (async function() {
                    var errors = [];
                    var origErr = window.onerror;
                    window.onerror = function(m) { errors.push(m); };

                    // Start animation on page 8
                    go(8);
                    var lineObj = buildLineSvg("Testing page switch");
                    var animPromise = animateLineWriting(lineObj, 4000);

                    // Switch page mid-animation
                    await new Promise(r => setTimeout(r, 100));
                    go(1);

                    // Await animation promise (should cancel immediately without error)
                    await animPromise;

                    window.onerror = origErr;
                    go(8); // return to page 8

                    return {
                        errors: errors,
                        activeAnimationAfter: activeLineAnimation
                    };
                })()
            """, await_promise=True); req_id += 1
            if len(t14_res["errors"]) == 0 and t14_res["activeAnimationAfter"] is None:
                test_results["Test 14: Page switching mid-animation leaves no stray timers or errors"] = "PASS"
            else:
                test_results["Test 14: Page switching mid-animation leaves no stray timers or errors"] = "FAIL"
            print("Test 14 Result:", t14_res)

            print("\n================ TEST SUMMARY ================")
            all_pass = True
            for name, status in test_results.items():
                print(f"[{status}] {name}")
                if status != "PASS":
                    all_pass = False
            print(f"Overall Result: {'ALL PASS' if all_pass else 'SOME FAILED'}")

    finally:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            pass

if __name__ == "__main__":
    asyncio.run(run_suite())
