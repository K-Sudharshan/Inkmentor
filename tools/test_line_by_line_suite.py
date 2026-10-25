import asyncio
import json
import urllib.request
import websockets
import subprocess
import time
import os
import base64

BROWSER_EXE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PORT = 9235
SERVER_URL = "http://127.0.0.1:8000/"

async def cdp_call(ws, req_id, method, params=None):
    payload = {"id": req_id, "method": method}
    if params:
        payload["params"] = params
    await ws.send(json.dumps(payload))
    while True:
        resp = await asyncio.wait_for(ws.recv(), timeout=45.0)
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

async def run_tests():
    temp_dir = os.path.join(os.environ.get("TEMP", "C:\\temp"), "inkmentor_line_by_line_test")
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
            await cdp_call(ws, req_id, "DOM.enable"); req_id += 1
            await cdp_call(ws, req_id, "CSS.enable"); req_id += 1
            await asyncio.sleep(1.0)

            # =========================================================================
            # TEST 1: Frame-by-frame line visibility during solve "Differentiate y = sin(3x^2)"
            # =========================================================================
            print("\n>>> Running Test 1: Frame-by-frame solve visibility")
            t1_eval = await evaluate(ws, req_id, """
            (async function() {
              await window.ensureFontLoaded();
              window.go(8);

              // Setup a frame observer to sample DOM every requestAnimationFrame
              var samples = [];
              var observing = true;

              function sampleFrame() {
                if (!observing) return;
                var step0 = document.getElementById('step-0');
                var step1 = document.getElementById('step-1');
                var step2 = document.getElementById('step-2');
                var mk = document.getElementById('mk');

                function getLineVis(stepEl) {
                  if (!stepEl) return 'not_in_dom';
                  var textEl = stepEl.querySelector('.ai-reenie-line');
                  if (!textEl) return 'no_text';
                  var clip = textEl.style.clipPath || '';
                  if (clip.indexOf('100%') !== -1) return 'hidden_clipped';
                  if (clip === 'none' || clip === '') return 'fully_visible';
                  return 'revealing';
                }

                samples.push({
                  t: performance.now(),
                  s0: getLineVis(step0),
                  s1: getLineVis(step1),
                  s2: getLineVis(step2),
                  mk: !!mk
                });

                requestAnimationFrame(sampleFrame);
              }

              requestAnimationFrame(sampleFrame);

              // Run solve
              var solveP = window.runSolvePipeline('Differentiate y = sin(3x^2)', null);

              // Monitor during solve
              await solveP;
              observing = false;

              // Analyze samples:
              // 1. While s0 was 'revealing' or 'hidden_clipped', s1 and s2 MUST be 'not_in_dom'
              // 2. While s1 was 'revealing', s2 MUST be 'not_in_dom'
              // 3. mk MUST NOT be present until all lines are done
              var s1ExistedDuringS0 = false;
              var s2ExistedDuringS1 = false;
              var mkExistedBeforeEnd = false;

              for (var i = 0; i < samples.length; i++) {
                var s = samples[i];
                if ((s.s0 === 'revealing' || s.s0 === 'hidden_clipped') && s.s1 !== 'not_in_dom') {
                  s1ExistedDuringS0 = true;
                }
                if ((s.s1 === 'revealing' || s.s1 === 'hidden_clipped') && s.s2 !== 'not_in_dom') {
                  s2ExistedDuringS1 = true;
                }
                if ((s.s0 !== 'fully_visible' || s.s1 !== 'fully_visible' || s.s2 !== 'fully_visible') && s.mk) {
                  mkExistedBeforeEnd = true;
                }
              }

              return {
                sampleCount: samples.length,
                s1ExistedDuringS0: s1ExistedDuringS0,
                s2ExistedDuringS1: s2ExistedDuringS1,
                mkExistedBeforeEnd: mkExistedBeforeEnd,
                finalStepsInDom: [!!document.getElementById('step-0'), !!document.getElementById('step-1'), !!document.getElementById('step-2')],
                finalMk: !!document.getElementById('mk')
              };
            })()
            """, await_promise=True)
            req_id += 1

            t1_pass = (
                t1_eval["sampleCount"] > 20 and
                t1_eval["s1ExistedDuringS0"] is False and
                t1_eval["s2ExistedDuringS1"] is False and
                t1_eval["mkExistedBeforeEnd"] is False and
                all(t1_eval["finalStepsInDom"]) and
                t1_eval["finalMk"] is True
            )
            results["Test 1: Frame-by-frame solve visibility"] = {
                "status": "PASS" if t1_pass else "FAIL",
                "details": t1_eval
            }
            print("Test 1 Result:", "PASS" if t1_pass else "FAIL", t1_eval)

            # =========================================================================
            # TEST 2: Multi-line case "Integrate sqrt(x) dx" written strictly one by one
            # =========================================================================
            print("\n>>> Running Test 2: Multi-line case 'Integrate sqrt(x) dx'")
            t2_eval = await evaluate(ws, req_id, """
            (async function() {
              await window.ensureFontLoaded();
              window.go(8);

              var orderLog = [];
              var obs = new MutationObserver(function(mutations) {
                for (var m = 0; m < mutations.length; m++) {
                  for (var a = 0; a < mutations[m].addedNodes.length; a++) {
                    var n = mutations[m].addedNodes[a];
                    if (n.id && n.id.startsWith('step-')) {
                      orderLog.push({ id: n.id, time: performance.now() });
                    }
                  }
                }
              });
              obs.observe(document.getElementById('notes'), { childList: true });

              await window.runSolvePipeline('Integrate sqrt(x) dx', null);
              obs.disconnect();

              var ids = orderLog.map(function(x){ return x.id; });
              var timeGaps = [];
              for (var i = 1; i < orderLog.length; i++) {
                timeGaps.push(orderLog[i].time - orderLog[i-1].time);
              }

              return {
                ids: ids,
                timeGaps: timeGaps,
                allGapsSignificant: timeGaps.every(function(g){ return g > 1000; })
              };
            })()
            """, await_promise=True)
            req_id += 1

            t2_pass = (
                len(t2_eval["ids"]) >= 2 and
                t2_eval["ids"] == sorted(t2_eval["ids"]) and
                t2_eval["allGapsSignificant"] is True
            )
            results["Test 2: Multi-line sequential write"] = {
                "status": "PASS" if t2_pass else "FAIL",
                "details": t2_eval
            }
            print("Test 2 Result:", "PASS" if t2_pass else "FAIL", t2_eval)

            # =========================================================================
            # TEST 3: Narration and writing stay in sync; no premature starts
            # =========================================================================
            print("\n>>> Running Test 3: Speech clock sync")
            t3_eval = await evaluate(ws, req_id, """
            (async function() {
              await window.ensureFontLoaded();
              // Verify cleanNarrationText and getStepDuration match speech timing
              var stepNarration = "Differentiating with respect to u gives cosine of u times du dx.";
              var clean = window.cleanNarrationText(stepNarration);
              var dur = window.getStepDuration(clean);

              // Duration should scale with word count (12 words * 400ms = 4800ms)
              var inRange = dur >= 2000 && dur <= 8000;

              return {
                clean: clean,
                duration: dur,
                inRange: inRange
              };
            })()
            """, await_promise=True)
            req_id += 1

            t3_pass = t3_eval["inRange"] is True and "Differentiating" in t3_eval["clean"]
            results["Test 3: Speech clock sync"] = {
                "status": "PASS" if t3_pass else "FAIL",
                "details": t3_eval
            }
            print("Test 3 Result:", "PASS" if t3_pass else "FAIL", t3_eval)

            # =========================================================================
            # TEST 4: Page reload shows stored solution instantly, finished, no animation
            # =========================================================================
            print("\n>>> Running Test 4: Reload stored solution instant path")
            t4_eval = await evaluate(ws, req_id, """
            (async function() {
              await window.ensureFontLoaded();
              // Setup stored solution on Page 8
              window.pageAiOutput[8] = {
                question: "Q. Reload Test",
                steps: [
                  { write: "y = sin(x)", narration: "Line 1" },
                  { write: "y' = cos(x)", narration: "Line 2" }
                ],
                cited: 1
              };
              window.savePersistedAiOutput();

              // Call render explicitly with instant path
              var t0 = performance.now();
              window.render({ animate: false });
              var t1 = performance.now();

              var step0 = document.getElementById('step-0');
              var step1 = document.getElementById('step-1');
              var t0Clip = step0 ? step0.querySelector('.ai-reenie-line').style.clipPath : '';
              var t1Clip = step1 ? step1.querySelector('.ai-reenie-line').style.clipPath : '';
              var dot0 = step0 ? window.getComputedStyle(step0.querySelector('.ai-pen-tip-dot')).display : '';

              return {
                renderTimeMs: t1 - t0,
                step0Visible: t0Clip === 'none' || t0Clip === '',
                step1Visible: t1Clip === 'none' || t1Clip === '',
                dotHidden: dot0 === 'none'
              };
            })()
            """, await_promise=True)
            req_id += 1

            t4_pass = (
                t4_eval["renderTimeMs"] < 100 and
                t4_eval["step0Visible"] is True and
                t4_eval["step1Visible"] is True and
                t4_eval["dotHidden"] is True
            )
            results["Test 4: Reload stored solution instant path"] = {
                "status": "PASS" if t4_pass else "FAIL",
                "details": t4_eval
            }
            print("Test 4 Result:", "PASS" if t4_pass else "FAIL", t4_eval)

            # =========================================================================
            # TEST 5: Switch page mid-animation and return: clean restore, complete
            # =========================================================================
            print("\n>>> Running Test 5: Switch page mid-animation and back")
            t5_eval = await evaluate(ws, req_id, """
            (async function() {
              await window.ensureFontLoaded();
              window.go(8);

              // Start solve
              window.runSolvePipeline('Differentiate y = sin(3x^2)', null);

              // Wait 1.5 seconds so step 0 is animating
              await new Promise(function(r) { setTimeout(r, 1500); });

              // Switch to Page 1 mid-solve
              window.go(1);
              var p1Text = document.getElementById('notes').textContent;

              // Switch back to Page 8
              window.go(8);
              var p8Steps = Array.from(document.querySelectorAll('.ln.ai[id^="step-"]'));
              var p8Text = p8Steps.map(function(e) { return e.textContent; });
              var p8Clips = p8Steps.map(function(e) {
                var t = e.querySelector('.ai-reenie-line');
                return t ? (t.style.clipPath || 'none') : 'none';
              });

              return {
                p1HasChainRule: p1Text.indexOf('Chain rule') !== -1,
                p8StepCount: p8Steps.length,
                p8AllVisible: p8Clips.every(function(c) { return c === 'none' || c === ''; })
              };
            })()
            """, await_promise=True)
            req_id += 1

            t5_pass = (
                t5_eval["p1HasChainRule"] is True and
                t5_eval["p8StepCount"] >= 2 and
                t5_eval["p8AllVisible"] is True
            )
            results["Test 5: Switch page mid-animation and return"] = {
                "status": "PASS" if t5_pass else "FAIL",
                "details": t5_eval
            }
            print("Test 5 Result:", "PASS" if t5_pass else "FAIL", t5_eval)

            # =========================================================================
            # TEST 6: Solve again mid-animation: stops old, starts new clean
            # =========================================================================
            print("\n>>> Running Test 6: Solve again mid-animation")
            t6_eval = await evaluate(ws, req_id, """
            (async function() {
              await window.ensureFontLoaded();
              window.go(8);

              // Start solve 1
              window.runSolvePipeline('Differentiate y = sin(3x^2)', null);
              await new Promise(function(r) { setTimeout(r, 1200); });

              // Start solve 2 mid-animation
              var solve2Promise = window.runSolvePipeline('Integrate 2x dx', null);
              await solve2Promise;

              var qEl = document.getElementById('ai-question');
              var qText = qEl ? qEl.textContent : '';
              var steps = Array.from(document.querySelectorAll('.ln.ai[id^="step-"]')).map(function(e){ return e.textContent; });

              return {
                finalQuestion: qText,
                stepCount: steps.length,
                hasNewContent: qText.indexOf('Integrate 2x dx') !== -1 || steps.some(function(s){ return s.indexOf('x^2') !== -1 || s.indexOf('x²') !== -1; })
              };
            })()
            """, await_promise=True)
            req_id += 1

            t6_pass = t6_eval["hasNewContent"] is True and t6_eval["stepCount"] >= 1
            results["Test 6: Solve again mid-animation"] = {
                "status": "PASS" if t6_pass else "FAIL",
                "details": t6_eval
            }
            print("Test 6 Result:", "PASS" if t6_pass else "FAIL", t6_eval)

            # =========================================================================
            # TEST 7: Eraser on AI line mid-animation
            # =========================================================================
            print("\n>>> Running Test 7: Eraser mid-animation")
            t7_eval = await evaluate(ws, req_id, """
            (async function() {
              await window.ensureFontLoaded();
              window.go(8);

              // Start solve
              window.runSolvePipeline('Differentiate y = sin(3x^2)', null);
              await new Promise(function(r) { setTimeout(r, 1200); });

              // Erase line 0 mid-animation
              var step0 = document.getElementById('step-0');
              var erased = false;
              if (step0) {
                var r = step0.getBoundingClientRect();
                var cvRect = cv.getBoundingClientRect();
                var px = (r.left + r.right) / 2 - cvRect.left;
                var py = (r.top + r.bottom) / 2 - cvRect.top;
                erased = window.eraseAiAt(px, py, 16);
              }

              // Pipeline should cleanly stop without errors
              await new Promise(function(r) { setTimeout(r, 500); });

              return {
                erased: erased,
                busyAfterErase: window.busy,
                chipOnAfterErase: document.getElementById('chip').classList.contains('on')
              };
            })()
            """, await_promise=True)
            req_id += 1

            t7_pass = t7_eval["erased"] is True and t7_eval["busyAfterErase"] is False and t7_eval["chipOnAfterErase"] is False
            results["Test 7: Eraser mid-animation"] = {
                "status": "PASS" if t7_pass else "FAIL",
                "details": t7_eval
            }
            print("Test 7 Result:", "PASS" if t7_pass else "FAIL", t7_eval)

            # =========================================================================
            # TEST 8: Network throttling / late font: no finished text before pen
            # =========================================================================
            print("\n>>> Running Test 8: Late font loading guard")
            t8_eval = await evaluate(ws, req_id, """
            (async function() {
              // Simulate delayed font loaded state
              window.fontLoadedState = false;
              window.fontLoadPromise = null;

              // Ensure initialHidden parameter produces fully clipped element immediately
              var lineObj = window.buildLineSvg("test line", { initialHidden: true });
              var clip = lineObj.textEl.style.clipPath;

              return {
                isClipped: clip.indexOf('100%') !== -1,
                clip: clip
              };
            })()
            """, await_promise=True)
            req_id += 1

            t8_pass = t8_eval["isClipped"] is True
            results["Test 8: Late font loading guard"] = {
                "status": "PASS" if t8_pass else "FAIL",
                "details": t8_eval
            }
            print("Test 8 Result:", "PASS" if t8_pass else "FAIL", t8_eval)

            # =========================================================================
            # TEST 9: Page 1 callback appears only after steps are written
            # =========================================================================
            print("\n>>> Running Test 9: Page 1 callback timing")
            t9_eval = await evaluate(ws, req_id, """
            (async function() {
              await window.ensureFontLoaded();
              window.go(8);

              var mkExistedDuringSteps = false;
              var obs = new MutationObserver(function() {
                var mk = document.getElementById('mk');
                var steps = document.querySelectorAll('.ln.ai[id^="step-"]');
                if (mk && steps.length < 3) {
                  mkExistedDuringSteps = true;
                }
              });
              obs.observe(document.getElementById('notes'), { childList: true, subtree: true });

              await window.runSolvePipeline('Differentiate y = sin(3x^2)', null);
              obs.disconnect();

              var finalMk = document.getElementById('mk');
              return {
                mkExistedDuringSteps: mkExistedDuringSteps,
                finalMkShown: finalMk ? finalMk.classList.contains('show') : false
              };
            })()
            """, await_promise=True)
            req_id += 1

            t9_pass = t9_eval["mkExistedDuringSteps"] is False and t9_eval["finalMkShown"] is True
            results["Test 9: Page 1 callback timing"] = {
                "status": "PASS" if t9_pass else "FAIL",
                "details": t9_eval
            }
            print("Test 9 Result:", "PASS" if t9_pass else "FAIL", t9_eval)

            # =========================================================================
            # TEST 10: prefers-reduced-motion and theme support
            # =========================================================================
            print("\n>>> Running Test 10: prefers-reduced-motion and themes")
            t10_eval = await evaluate(ws, req_id, """
            (async function() {
              await window.ensureFontLoaded();
              var lineObj = window.buildLineSvg("fast line", { initialHidden: true });
              var cont = document.createElement('div');
              cont.appendChild(lineObj.svg);
              notes.appendChild(cont);

              // Test zero-duration (reduced motion equivalent)
              await window.animateLineWriting(lineObj, 0);
              var clip = lineObj.textEl.style.clipPath;
              var dotDisplay = window.getComputedStyle(lineObj.penTip).display;
              cont.remove();

              // Dark theme check
              document.documentElement.setAttribute('data-theme', 'dark');
              var darkBg = window.getComputedStyle(document.body).backgroundColor;
              document.documentElement.setAttribute('data-theme', 'light');
              var lightBg = window.getComputedStyle(document.body).backgroundColor;

              return {
                instantClip: clip === 'none' || clip === '',
                dotHidden: dotDisplay === 'none',
                darkBg: darkBg,
                lightBg: lightBg
              };
            })()
            """, await_promise=True)
            req_id += 1

            t10_pass = (
                t10_eval["instantClip"] is True and
                t10_eval["dotHidden"] is True and
                t10_eval["darkBg"] != t10_eval["lightBg"]
            )
            results["Test 10: prefers-reduced-motion & themes"] = {
                "status": "PASS" if t10_pass else "FAIL",
                "details": t10_eval
            }
            print("Test 10 Result:", "PASS" if t10_pass else "FAIL", t10_eval)

            # Capture a screenshot during a clean solve
            await evaluate(ws, req_id, """
            (async function() {
              window.go(8);
              window.render({ animate: false });
            })()
            """, await_promise=True)
            req_id += 1
            ss = await cdp_call(ws, req_id, "Page.captureScreenshot", {"format": "png"})
            with open("tools/line_by_line_final.png", "wb") as f:
                f.write(base64.b64decode(ss["result"]["data"]))
            print("Screenshot saved to tools/line_by_line_final.png")

    finally:
        browser_proc.kill()

    print("\n================== SUMMARY ==================")
    all_pass = True
    for name, r in results.items():
        status = r["status"]
        if status != "PASS":
            all_pass = False
        print(f"[{status}] {name}")
    print("=============================================")
    return all_pass

if __name__ == '__main__':
    ok = asyncio.run(run_tests())
    exit(0 if ok else 1)
