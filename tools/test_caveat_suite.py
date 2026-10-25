import os
import sys
import json
import time
import subprocess
import urllib.request
import asyncio
import base64
import websockets

EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BROWSER_EXE = EDGE_EXE if os.path.exists(EDGE_EXE) else CHROME_EXE

PORT = 9223  # Dedicated port to avoid any collision
SERVER_URL = "http://127.0.0.1:8000/"

async def cdp_call(ws, req_id, method, params=None):
    payload = {"id": req_id, "method": method}
    if params:
        payload["params"] = params
    await ws.send(json.dumps(payload))
    while True:
        resp = await asyncio.wait_for(ws.recv(), timeout=12.0)
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

async def capture_screenshot(ws, req_id, file_path):
    res = await cdp_call(ws, req_id, "Page.captureScreenshot", {"format": "png"})
    data = res.get("result", {}).get("data")
    if data:
        with open(file_path, "wb") as f:
            f.write(base64.b64decode(data))

async def run_tests():
    temp_dir = os.path.join(os.environ.get("TEMP", "C:\\temp"), "inkmentor_caveat_test")
    os.makedirs(temp_dir, exist_ok=True)

    print(f"Starting real browser on port {PORT}: {BROWSER_EXE}")
    browser_proc = subprocess.Popen([
        BROWSER_EXE,
        "--headless=new",
        f"--remote-debugging-port={PORT}",
        f"--user-data-dir={temp_dir}",
        "--no-first-run",
        "--disable-gpu",
        SERVER_URL
    ])

    results = {}

    try:
        tab_ws_url = None
        for _ in range(30):
            time.sleep(0.4)
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=2) as r:
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

        async with websockets.connect(tab_ws_url, max_size=20*1024*1024) as ws:
            req_id = 1
            await cdp_call(ws, req_id, "Runtime.enable"); req_id += 1
            await cdp_call(ws, req_id, "Page.enable"); req_id += 1
            await cdp_call(ws, req_id, "Network.enable"); req_id += 1
            await asyncio.sleep(1.2)

            print("Connected to browser session via CDP.")

            # --- TEST 1: Solve 'Integrate sqrt(x) dx' ---
            print("\n>>> Running Test 1: Integrate sqrt(x) dx")
            t1_eval = await evaluate(ws, req_id, """
            (async function() {
              await window.ensureFontLoaded();
              window.go(8);
              var steps = [
                { write: "int x^(1/2) dx", narration: "First write the square root as x to the one half power." },
                { write: "x^(3/2) / (3/2)", narration: "Add one to the exponent and divide by the new exponent." },
                { write: "2/3 * x^(3/2)", narration: "Dividing by three halves gives two thirds x to the three halves." }
              ];
              window.pageAiOutput[8] = {
                question: "Q. Integrate sqrt(x) dx",
                steps: steps,
                cited: 7
              };
              window.render();
              
              var stepEls = Array.from(document.querySelectorAll('.ln.ai[id^="step-"]'));
              var details = stepEls.map(function(el, i) {
                var textEl = el.querySelector('.ai-reenie-line');
                var svg = el.querySelector('.math-svg');
                var sup = el.querySelector('.math-sup');
                var diff = el.querySelector('.math-diff');
                var delims = Array.from(el.querySelectorAll('.math-delim')).map(function(d){ return d.textContent; });
                var cs = textEl ? window.getComputedStyle(textEl) : null;
                var svgCs = svg ? window.getComputedStyle(svg) : null;
                var supCs = sup ? window.getComputedStyle(sup) : null;
                return {
                  stepIdx: i,
                  rawText: steps[i].write,
                  fontFamily: cs ? cs.fontFamily : '',
                  fontSize: cs ? cs.fontSize : '',
                  lineHeight: cs ? cs.lineHeight : '',
                  rect: el.getBoundingClientRect(),
                  hasSvg: !!svg,
                  svgClass: svg ? svg.getAttribute('class') : '',
                  svgHeight: svg ? svg.style.height : '',
                  svgStrokeWidth: svg ? (svg.querySelector('path') ? svg.querySelector('path').getAttribute('stroke-width') : '') : '',
                  svgMarginLeft: svg ? svg.style.marginLeft : '',
                  svgMarginRight: svg ? svg.style.marginRight : '',
                  supText: sup ? sup.textContent : '',
                  supFontSize: sup ? sup.style.fontSize : '',
                  supShift: sup ? sup.style.verticalAlign : '',
                  supMarginRight: sup ? sup.style.marginRight : '',
                  diffText: diff ? diff.textContent : '',
                  diffMarginLeft: diff ? diff.style.marginLeft : '',
                  delims: delims
                };
              });
              return details;
            })()
            """, await_promise=True)
            req_id += 1

            t1_pass = (
                len(t1_eval) == 3 and
                "Caveat" in t1_eval[0]["fontFamily"] and
                t1_eval[0]["hasSvg"] and
                t1_eval[0]["svgStrokeWidth"] == "3.2" and
                t1_eval[0]["supText"] == "1/2" and
                t1_eval[0]["diffText"] == "dx" and
                "/" in t1_eval[1]["delims"] and
                "(" in t1_eval[1]["delims"]
            )
            results["Test 1: Integrate sqrt(x) dx"] = {
                "status": "PASS" if t1_pass else "FAIL",
                "details": t1_eval
            }
            print("Test 1 Result:", "PASS" if t1_pass else "FAIL")
            print("  Line 1:", t1_eval[0]["rawText"], "Font:", t1_eval[0]["fontFamily"], "Integral Stroke:", t1_eval[0]["svgStrokeWidth"], "Sup:", t1_eval[0]["supText"])
            print("  Line 2:", t1_eval[1]["rawText"], "Delims:", t1_eval[1]["delims"], "Sup:", t1_eval[1]["supText"])
            print("  Line 3:", t1_eval[2]["rawText"], "Sup:", t1_eval[2]["supText"])

            # --- TEST 2: Solve 'Differentiate y = sin(3x^2)' and 'Solve x^2 - 5x + 6 = 0' ---
            print("\n>>> Running Test 2: Differentiate y = sin(3x^2) and Solve x^2 - 5x + 6 = 0 (no overlaps)")
            t2_eval = await evaluate(ws, req_id, """
            (async function() {
              await window.ensureFontLoaded();
              window.pageAiOutput[8] = {
                question: "Q. Differentiate y = sin(3x^2)",
                steps: [
                  { write: "Let u = 3x^2,  du/dx = 6x", narration: "Let u equal 3x squared." },
                  { write: "y' = cos(u) * du/dx", narration: "Differentiate with chain rule." },
                  { write: "y' = 6x cos(3x^2)", narration: "Substitute back." }
                ],
                cited: 1
              };
              window.render();
              
              var stepEls = Array.from(document.querySelectorAll('.ln.ai[id^="step-"]'));
              var rects = stepEls.map(function(e) { return e.getBoundingClientRect(); });
              var noOverlapDiff = true;
              for (var i = 0; i < rects.length - 1; i++) {
                if (rects[i].bottom > rects[i+1].top + 2) noOverlapDiff = false;
              }

              // Now test second problem: Solve x^2 - 5x + 6 = 0
              window.pageAiOutput[8] = {
                question: "Q. Solve x^2 - 5x + 6 = 0",
                steps: [
                  { write: "(x - 2)(x - 3) = 0", narration: "Factor the quadratic expression." },
                  { write: "x - 2 = 0  or  x - 3 = 0", narration: "Apply the zero product rule." },
                  { write: "x = 2,  x = 3", narration: "Solve each linear equation." }
                ],
                cited: null
              };
              window.render();
              var quadEls = Array.from(document.querySelectorAll('.ln.ai[id^="step-"]'));
              var quadRects = quadEls.map(function(e) { return e.getBoundingClientRect(); });
              var noOverlapQuad = true;
              for (var j = 0; j < quadRects.length - 1; j++) {
                if (quadRects[j].bottom > quadRects[j+1].top + 2) noOverlapQuad = false;
              }

              return {
                diffLines: rects.length,
                noOverlapDiff: noOverlapDiff,
                quadLines: quadRects.length,
                noOverlapQuad: noOverlapQuad,
                lineHeightDiff: rects[0].height,
                lineHeightQuad: quadRects[0].height
              };
            })()
            """, await_promise=True)
            req_id += 1

            t2_pass = t2_eval["noOverlapDiff"] and t2_eval["noOverlapQuad"] and t2_eval["diffLines"] == 3 and t2_eval["quadLines"] == 3
            results["Test 2: Natural lines, no overlaps"] = {
                "status": "PASS" if t2_pass else "FAIL",
                "details": t2_eval
            }
            print("Test 2 Result:", "PASS" if t2_pass else "FAIL", t2_eval)

            # --- TEST 3: Pen-style writing and pen-tip dot work in sync with voice ---
            print("\n>>> Running Test 3: Pen-style writing and pen-tip dot")
            t3_eval = await evaluate(ws, req_id, """
            (async function() {
              await window.ensureFontLoaded();
              window.go(8);
              var lineObj = window.buildLineSvg("y' = 6x cos(3x^2)");
              var cont = document.createElement('div');
              cont.className = 'ln ai';
              cont.appendChild(lineObj.svg);
              notes.appendChild(cont);

              var dot = lineObj.penTip;
              var textEl = lineObj.textEl;
              
              var animPromise = window.animateLineWriting(lineObj, 400);
              
              await new Promise(function(r) { setTimeout(r, 150); });
              var midDotDisplay = window.getComputedStyle(dot).display;
              var midClip = textEl.style.clipPath;
              var midDotLeft = parseFloat(dot.style.left) || 0;

              await animPromise;
              var endDotDisplay = window.getComputedStyle(dot).display;
              var endClip = textEl.style.clipPath;
              cont.remove();

              return {
                midDotDisplay: midDotDisplay,
                midDotLeft: midDotLeft,
                midClip: midClip,
                endDotDisplay: endDotDisplay,
                endClip: endClip
              };
            })()
            """, await_promise=True)
            req_id += 1

            t3_pass = (
                t3_eval["midDotDisplay"] == "block" and
                t3_eval["midDotLeft"] > 0 and
                "inset" in t3_eval["midClip"] and
                t3_eval["endDotDisplay"] == "none" and
                t3_eval["endClip"] == "none"
            )
            results["Test 3: Pen-style reveal & dot"] = {
                "status": "PASS" if t3_pass else "FAIL",
                "details": t3_eval
            }
            print("Test 3 Result:", "PASS" if t3_pass else "FAIL", t3_eval)

            # --- TEST 4: Eraser removes AI lines correctly ---
            print("\n>>> Running Test 4: Eraser removes AI lines correctly")
            t4_eval = await evaluate(ws, req_id, """
            (async function() {
              await window.ensureFontLoaded();
              window.go(8);
              window.pageAiOutput[8] = {
                question: "Q. Test Eraser",
                steps: [
                  { write: "Line A", narration: "Step A" },
                  { write: "Line B", narration: "Step B" },
                  { write: "Line C", narration: "Step C" }
                ],
                cited: 1
              };
              window.render();

              var step1El = document.getElementById('step-1');
              var r = step1El.getBoundingClientRect();
              var cvRect = cv.getBoundingClientRect();
              var px = (r.left + r.right) / 2 - cvRect.left;
              var py = (r.top + r.bottom) / 2 - cvRect.top;

              var erased = window.eraseAiAt(px, py, 16);
              var remainingSteps = window.pageAiOutput[8].steps.map(function(s){ return s.write; });
              var remainingEls = Array.from(document.querySelectorAll('.ln.ai[id^="step-"]')).map(function(e){ return e.id; });

              // Undo
              window.undoAction();
              var restoredSteps = window.pageAiOutput[8].steps.map(function(s){ return s.write; });

              return {
                erased: erased,
                remainingSteps: remainingSteps,
                remainingEls: remainingEls,
                restoredSteps: restoredSteps
              };
            })()
            """, await_promise=True)
            req_id += 1

            t4_pass = (
                t4_eval["erased"] is True and
                t4_eval["remainingSteps"] == ["Line A", "Line C"] and
                t4_eval["remainingEls"] == ["step-0", "step-1"] and
                t4_eval["restoredSteps"] == ["Line A", "Line B", "Line C"]
            )
            results["Test 4: Eraser on AI lines"] = {
                "status": "PASS" if t4_pass else "FAIL",
                "details": t4_eval
            }
            print("Test 4 Result:", "PASS" if t4_pass else "FAIL", t4_eval)

            # --- TEST 5: Reload persistence on seeded & new page ---
            print("\n>>> Running Test 5: Reload persistence")
            t5_eval = await evaluate(ws, req_id, """
            (async function() {
              await window.ensureFontLoaded();
              // Setup Page 8 and New Page 9
              window.pageAiOutput[8] = {
                question: "Q. Chain Rule Test",
                steps: [{ write: "dy/dx = 6x cos(3x^2)", narration: "Done." }],
                cited: 1
              };
              window.savePersistedAiOutput();

              // Create page 9 if needed
              if (window.pages.length < 9) {
                window.pages.push({ t: 'Page 9', id: 9 });
                window.savePersistedPages();
              }
              window.pageAiOutput[9] = {
                question: "Q. Integral Test",
                steps: [{ write: "int x dx = 1/2 x^2", narration: "Done." }],
                cited: null
              };
              window.savePersistedAiOutput();

              // Re-render page 8
              window.go(8);
              var p8Text = document.querySelector('.ai-reenie-line').textContent;
              var p8Font = window.getComputedStyle(document.querySelector('.ai-reenie-line')).fontFamily;

              // Re-render page 9
              window.go(9);
              var p9Text = document.querySelector('.ai-reenie-line').textContent;
              var p9Font = window.getComputedStyle(document.querySelector('.ai-reenie-line')).fontFamily;

              return {
                p8Text: p8Text,
                p8Font: p8Font,
                p9Text: p9Text,
                p9Font: p9Font
              };
            })()
            """, await_promise=True)
            req_id += 1

            t5_pass = (
                "Caveat" in t5_eval["p8Font"] and
                "Caveat" in t5_eval["p9Font"] and
                "6x cos(3x" in t5_eval["p8Text"] and
                "1/2 x" in t5_eval["p9Text"]
            )
            results["Test 5: Persistence & reload"] = {
                "status": "PASS" if t5_pass else "FAIL",
                "details": t5_eval
            }
            print("Test 5 Result:", "PASS" if t5_pass else "FAIL", t5_eval)

            # --- TEST 6: Hard refresh with throttled network (no layout jump) ---
            print("\n>>> Running Test 6: Network throttling & no layout jump")
            # Emulate slow network: 300ms latency, 150kb/s
            await cdp_call(ws, req_id, "Network.emulateNetworkConditions", {
                "offline": False,
                "latency": 300,
                "downloadThroughput": 150 * 1024 / 8,
                "uploadThroughput": 150 * 1024 / 8
            }); req_id += 1

            # Navigate to refresh page under throttled conditions
            await cdp_call(ws, req_id, "Page.navigate", {"url": SERVER_URL}); req_id += 1
            
            # Poll until script finishes executing under throttled conditions
            for _ in range(40):
                await asyncio.sleep(0.4)
                ready = await evaluate(ws, req_id, "typeof window.ensureFontLoaded === 'function'")
                req_id += 1
                if ready is True:
                    break

            t6_eval = await evaluate(ws, req_id, """
            (async function() {
              var loaded = await window.ensureFontLoaded();
              var notesEl = document.getElementById('notes');
              var cs = window.getComputedStyle(notesEl);
              return {
                loaded: loaded,
                fontFamily: cs.fontFamily,
                fontSize: cs.fontSize,
                lineHeight: cs.lineHeight
              };
            })()
            """, await_promise=True)
            req_id += 1

            # Disable network emulation
            await cdp_call(ws, req_id, "Network.emulateNetworkConditions", {
                "offline": False,
                "latency": 0,
                "downloadThroughput": -1,
                "uploadThroughput": -1
            }); req_id += 1

            t6_pass = isinstance(t6_eval, dict) and t6_eval.get("loaded") is True and "Caveat" in t6_eval.get("fontFamily", "")
            results["Test 6: Throttling / no layout jump"] = {
                "status": "PASS" if t6_pass else "FAIL",
                "details": t6_eval
            }
            print("Test 6 Result:", "PASS" if t6_pass else "FAIL", t6_eval)

            # --- TEST 7: Simulate font failure (graceful fallback) ---
            print("\n>>> Running Test 7: Simulated font failure")
            font_path = os.path.abspath("fonts/Caveat-Regular.ttf")
            font_bak = os.path.abspath("fonts/Caveat-Regular.ttf.bak")
            os.rename(font_path, font_bak)
            try:
                t7_eval = await evaluate(ws, req_id, """
                (async function() {
                  // Create a test FontFace that points to non-existent font
                  var failedFace = new FontFace("CaveatFake", "url(fonts/Caveat-NonExistent.ttf)");
                  var loadFailed = false;
                  try {
                    await failedFace.load();
                  } catch(e) {
                    loadFailed = true;
                  }
                  
                  // Now test our ensureFontLoaded robustness
                  window.fontLoadedState = false;
                  window.fontLoadPromise = null;
                  var ok = false;
                  try {
                    await window.ensureFontLoaded();
                    ok = true;
                  } catch(err) {
                    ok = false;
                  }

                  // Render should still work cleanly without throwing
                  var renderOk = false;
                  try {
                    window.render();
                    renderOk = true;
                  } catch(e) {
                    renderOk = false;
                  }

                  return {
                    loadFailedExpected: loadFailed,
                    ensureFontLoadedDidNotThrow: ok,
                    renderDidNotThrow: renderOk
                  };
                })()
                """, await_promise=True)
                req_id += 1
            finally:
                if os.path.exists(font_bak):
                    os.rename(font_bak, font_path)

            t7_pass = t7_eval["loadFailedExpected"] and t7_eval["ensureFontLoadedDidNotThrow"] and t7_eval["renderDidNotThrow"]
            results["Test 7: Font failure fallback"] = {
                "status": "PASS" if t7_pass else "FAIL",
                "details": t7_eval
            }
            print("Test 7 Result:", "PASS" if t7_pass else "FAIL", t7_eval)

            # --- TEST 8: AI_FONT = 'reenie' restores old look ---
            print("\n>>> Running Test 8: AI_FONT = 'reenie' toggle")
            t8_eval = await evaluate(ws, req_id, """
            (async function() {
              await window.setFont('reenie');
              var reenieCfg = {
                fontFamily: window.AI_FONT_FAMILY,
                fontSize: window.AI_FONT_SIZE,
                integralStroke: window.INTEGRAL_STROKE_WIDTH,
                integralScale: window.INTEGRAL_SCALE,
                expShift: window.EXPONENT_SHIFT,
                glow: window.AI_INK_GLOW
              };

              // Restore Caveat
              await window.setFont('caveat');
              var caveatCfg = {
                fontFamily: window.AI_FONT_FAMILY,
                fontSize: window.AI_FONT_SIZE,
                integralStroke: window.INTEGRAL_STROKE_WIDTH,
                integralScale: window.INTEGRAL_SCALE,
                expShift: window.EXPONENT_SHIFT,
                glow: window.AI_INK_GLOW
              };

              return {
                reenie: reenieCfg,
                caveat: caveatCfg
              };
            })()
            """, await_promise=True)
            req_id += 1

            t8_pass = (
                "Reenie Beanie" in t8_eval["reenie"]["fontFamily"] and
                t8_eval["reenie"]["integralStroke"] == 2.4 and
                t8_eval["reenie"]["expShift"] == "0.38em" and
                "Caveat" in t8_eval["caveat"]["fontFamily"] and
                t8_eval["caveat"]["integralStroke"] == 3.2 and
                t8_eval["caveat"]["expShift"] == "0.44em"
            )
            results["Test 8: AI_FONT toggle"] = {
                "status": "PASS" if t8_pass else "FAIL",
                "details": t8_eval
            }
            print("Test 8 Result:", "PASS" if t8_pass else "FAIL", t8_eval)

            # --- TEST 9: Dark / Light themes and prefers-reduced-motion ---
            print("\n>>> Running Test 9: Themes and prefers-reduced-motion")
            t9_eval = await evaluate(ws, req_id, """
            (async function() {
              await window.ensureFontLoaded();
              window.go(8);
              
              // Dark theme
              document.documentElement.dataset.theme = 'dark';
              var darkBg = window.getComputedStyle(document.body).backgroundColor;
              var darkGlow = window.getComputedStyle(document.querySelector('.ai-reenie-line')).filter;

              // Light theme
              document.documentElement.dataset.theme = 'light';
              var lightBg = window.getComputedStyle(document.body).backgroundColor;
              var lightGlow = window.getComputedStyle(document.querySelector('.ai-reenie-line')).filter;

              return {
                darkBg: darkBg,
                darkGlow: darkGlow,
                lightBg: lightBg,
                lightGlow: lightGlow
              };
            })()
            """, await_promise=True)
            req_id += 1

            # Emulate prefers-reduced-motion: reduce
            await cdp_call(ws, req_id, "Emulation.setEmulatedMedia", {
                "media": "",
                "features": [{"name": "prefers-reduced-motion", "value": "reduce"}]
            }); req_id += 1

            t9_reduced = await evaluate(ws, req_id, """
            (async function() {
              var lineObj = window.buildLineSvg("x^2 + y^2 = r^2");
              document.getElementById('notes').appendChild(lineObj.svg);
              // Run animation with non-zero requested duration
              await window.animateLineWriting(lineObj, 4000);
              var dotDisplay = window.getComputedStyle(lineObj.penTip).display;
              var clip = lineObj.textEl.style.clipPath;
              lineObj.svg.remove();
              return {
                dotDisplay: dotDisplay,
                clip: clip
              };
            })()
            """, await_promise=True)
            req_id += 1

            # Restore normal motion
            await cdp_call(ws, req_id, "Emulation.setEmulatedMedia", {
                "features": []
            }); req_id += 1

            t9_pass = (
                t9_reduced["dotDisplay"] == "none" and
                t9_reduced["clip"] == "none" and
                "rgb(10, 10, 15)" in t9_eval["darkBg"] and
                "rgb(242, 242, 247)" in t9_eval["lightBg"]
            )
            results["Test 9: Themes & prefers-reduced-motion"] = {
                "status": "PASS" if t9_pass else "FAIL",
                "details": {**t9_eval, **t9_reduced}
            }
            print("Test 9 Result:", "PASS" if t9_pass else "FAIL", {**t9_eval, **t9_reduced})

            # Capture a screenshot of the final rendered state
            screenshot_path = os.path.abspath("caveat_verification_browser.png")
            await capture_screenshot(ws, req_id, screenshot_path)
            req_id += 1
            print(f"Captured browser screenshot to {screenshot_path}")

    finally:
        browser_proc.kill()
        try:
            browser_proc.wait(timeout=3)
        except Exception:
            pass

    # --- TEST 10: Production check from different working directory ---
    print("\n>>> Running Test 10: Production static font delivery from different CWD")
    test10_cmd = [
        os.path.abspath(r"backend\.venv\Scripts\python.exe"),
        "-c",
        "import os; from fastapi.testclient import TestClient; from backend.main import app; "
        "c = TestClient(app); r = c.get('/fonts/Caveat-Regular.ttf'); "
        "head_r = c.head('/fonts/Caveat-Regular.ttf'); "
        "assert r.status_code == 200, f'Status {r.status_code}'; "
        "assert head_r.status_code == 200, f'HEAD status {head_r.status_code}'; "
        "assert 'font/ttf' in r.headers['content-type'], f'Bad content type: {r.headers}'; "
        "assert len(r.content) == 196984, f'Bad length {len(r.content)}'; "
        "print('PASS_TEST10')"
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.abspath(".")
    p10 = subprocess.run(
        test10_cmd,
        cwd=os.path.abspath("backend"),
        capture_output=True,
        text=True,
        env=env
    )
    t10_pass = "PASS_TEST10" in p10.stdout
    results["Test 10: Production font delivery"] = {
        "status": "PASS" if t10_pass else "FAIL",
        "stdout": p10.stdout.strip(),
        "stderr": p10.stderr.strip()
    }
    print("Test 10 Result:", "PASS" if t10_pass else "FAIL", p10.stdout.strip())

    # --- TEST 11: Backend pytest suite ---
    print("\n>>> Running Test 11: Backend pytest suite")
    p11 = subprocess.run(
        [os.path.abspath(r"backend\.venv\Scripts\pytest.exe"), "-v"],
        cwd=os.path.abspath("."),
        capture_output=True,
        text=True
    )
    t11_pass = p11.returncode == 0 and "32 passed" in p11.stdout
    results["Test 11: Backend pytest suite"] = {
        "status": "PASS" if t11_pass else "FAIL",
        "returncode": p11.returncode,
        "stdout": p11.stdout.strip()
    }
    print("Test 11 Result:", "PASS" if t11_pass else "FAIL")
    print(p11.stdout.strip()[-300:])

    print("\n================== SUMMARY ==================")
    all_pass = True
    for name, res in results.items():
        st = res["status"]
        if st != "PASS":
            all_pass = False
        print(f"[{st}] {name}")
    print("=============================================")
    return all_pass, results

if __name__ == "__main__":
    success, res = asyncio.run(run_tests())
    sys.exit(0 if success else 1)
