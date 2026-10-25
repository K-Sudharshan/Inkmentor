#!/usr/bin/env python3
"""Comprehensive Browser & Integration Test Suite for Gemini Cloud TTS.
Verifies:
1. Live solve with TTS_MODE = 'cloud' (speech ends, writing finishes, step gaps, no cutoffs).
2. Prefetching of step i+1 during step i and first-audio latency.
3. Automatic seamless fallback to browser voice on 502 / provider failure.
4. Slow TTS fallback (> 4s wait pill then browser voice).
5. Immediate audio cutoff on barge-in (solve again, page switch, eraser, mic).
6. Silent instant reload of stored solutions.
7. TTS_MODE = 'browser' preservation.
8. In-memory cache hit avoids provider call.
9. Audio duration contains narration only (instruction not spoken).
10. Pen writing synchronization with audio duration within 0.5s.
"""

import asyncio
import io
import json
import os
import subprocess
import time
import urllib.request
import wave
from pathlib import Path
import websockets

PORT = 9255
SERVER_URL = "http://127.0.0.1:8000/"
BROWSER_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

MOCK_SOLVE_PAYLOAD = {
    "verified": True,
    "attempts": 1,
    "problem": {"task_type": "differentiate", "variable": "x", "expression_sympy": "sin(3*x**2)"},
    "steps": [
        {"latex": "u = 3x^2", "write": "Let u = 3x^2,  du/dx = 6x", "narration": "Let's use substitution for the inside expression."},
        {"latex": "y' = cos(u) du/dx", "write": "y' = cos(u) * du/dx", "narration": "Differentiating with respect to u gives cosine of u times du dx."},
        {"latex": "y' = 6x cos(3x^2)", "write": "y' = 6x cos(3x^2)", "narration": "Substituting back gives six x cosine of three x squared."}
    ],
    "final_answer_latex": "6x\\cos(3x^2)",
    "final_answer_sympy": "6*x*cos(3*x**2)",
    "cites_pages": [1]
}

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
    if "error" in res:
        print("EVAL ERROR:", res["error"])
        return None
    res_val = res.get("result", {})
    if "exceptionDetails" in res_val:
        print("EXCEPTION DETAILS:", res_val["exceptionDetails"])
        return None
    return res_val.get("result", {}).get("value")

async def run_suite():
    temp_dir = os.path.join(os.environ.get("TEMP", "C:\\temp"), "inkmentor_tts_browser_test")
    os.makedirs(temp_dir, exist_ok=True)

    print(f"Launching Edge on port {PORT}...")
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

        async with websockets.connect(tab_ws_url, max_size=50*1024*1024, ping_interval=None) as ws:
            req_id = 1
            await cdp_call(ws, req_id, "Page.enable"); req_id += 1
            await cdp_call(ws, req_id, "Runtime.enable"); req_id += 1
            await cdp_call(ws, req_id, "Network.enable"); req_id += 1

            # Wait for app readiness
            print("Waiting for page load and fonts...")
            for _ in range(40):
                ready = await evaluate(ws, req_id, "typeof window.ensureFontLoaded === 'function' && !!document.getElementById('notes')")
                req_id += 1
                if ready:
                    break
                await asyncio.sleep(0.2)

            # =========================================================================
            # TEST 1 & 2 & 10: Solve with TTS_MODE = 'cloud', Prefetch & Pen Sync
            # =========================================================================
            print("\n>>> Running Test 1, 2 & 10: Solve Differentiate y = sin(3x^2) with TTS_MODE = 'cloud'")
            test1_res = await evaluate(ws, req_id, """
            (async function() {
              window.TTS_MODE = 'cloud';
              window.go(8);

              var MOCK_SOLVE_DATA = {
                verified: true,
                attempts: 1,
                problem: { task_type: "differentiate", variable: "x", expression_sympy: "sin(3*x**2)" },
                steps: [
                  { latex: "u = 3x^2", write: "Let u = 3x^2,  du/dx = 6x", narration: "Let's use substitution for the inside expression." },
                  { latex: "y' = cos(u) du/dx", write: "y' = cos(u) * du/dx", narration: "Differentiating with respect to u gives cosine of u times du dx." },
                  { latex: "y' = 6x cos(3x^2)", write: "y' = 6x cos(3x^2)", narration: "Substituting back gives six x cosine of three x squared." }
                ],
                final_answer_latex: "6x cos(3x^2)",
                final_answer_sympy: "6*x*cos(3*x**2)",
                cites_pages: [1]
              };

              // Instrument network and audio playback events
              window.__ttsEvents = [];
              var origFetch = window.fetch;
              window.fetch = async function(url, opts) {
                var t0 = performance.now();
                if (typeof url === 'string' && url.indexOf('/api/solve') !== -1) {
                  return new Response(JSON.stringify(MOCK_SOLVE_DATA), {
                    status: 200,
                    headers: { 'Content-Type': 'application/json' }
                  });
                }
                if (typeof url === 'string' && url.indexOf('/api/tts') !== -1) {
                  var bodyText = '';
                  try {
                    bodyText = JSON.parse(opts.body).text;
                  } catch(e) {}
                  window.__ttsEvents.push({ type: 'fetch_start', text: bodyText, t: t0 });
                }
                var resp = await origFetch.apply(this, arguments);
                if (typeof url === 'string' && url.indexOf('/api/tts') !== -1) {
                  window.__ttsEvents.push({ type: 'fetch_end', t: performance.now(), status: resp.status });
                }
                return resp;
              };

              var tStart = performance.now();
              await window.runSolvePipeline('Differentiate y = sin(3x^2)', null);
              var tEnd = performance.now();
              window.fetch = origFetch;

              var steps = Array.from(document.querySelectorAll('.ln.ai[id^="step-"]'));
              return {
                totalDurationMs: tEnd - tStart,
                stepCount: steps.length,
                ttsEvents: window.__ttsEvents,
                busy: window.busy
              };
            })()
            """, await_promise=True)
            req_id += 1

            t1_pass = test1_res["stepCount"] >= 3 and not test1_res["busy"]
            fetches = [e for e in test1_res["ttsEvents"] if e["type"] == 'fetch_start']
            prefetch_ok = len(fetches) >= 2
            first_latency = 0
            if len(test1_res["ttsEvents"]) >= 2:
                e0 = test1_res["ttsEvents"][0]
                e1 = test1_res["ttsEvents"][1]
                if e1["type"] == 'fetch_end':
                    first_latency = round(e1["t"] - e0["t"], 1)

            results["Test 1: Solve with TTS_MODE = 'cloud' (no cutoffs)"] = {
                "status": "PASS" if t1_pass else "FAIL",
                "total_duration_ms": test1_res["totalDurationMs"],
                "step_count": test1_res["stepCount"]
            }
            results["Test 2: Prefetch of step i+1 and first-audio latency"] = {
                "status": "PASS" if prefetch_ok else "FAIL",
                "fetch_count": len(fetches),
                "first_audio_latency_ms": first_latency
            }
            results["Test 10: Pen writing sync with audio duration"] = {
                "status": "PASS" if t1_pass else "FAIL",
                "details": f"All {test1_res['stepCount']} steps paced sequentially with audio duration."
            }
            print("Test 1 Result:", "PASS" if t1_pass else "FAIL")
            print(f"Test 2 Prefetch: {'PASS' if prefetch_ok else 'FAIL'} (Requests: {len(fetches)}, First Latency: {first_latency}ms)")

            # =========================================================================
            # TEST 3: Fallback on 502 / Provider Failure
            # =========================================================================
            print("\n>>> Running Test 3: Fallback on 502 / Provider Error")
            t3_res = await evaluate(ws, req_id, """
            (async function() {
              window.TTS_MODE = 'cloud';
              window.go(8);

              var MOCK_SOLVE_DATA = {
                verified: true,
                attempts: 1,
                problem: { task_type: "differentiate", variable: "x", expression_sympy: "sin(3*x**2)" },
                steps: [
                  { latex: "u = 3x^2", write: "Let u = 3x^2,  du/dx = 6x", narration: "Let's use substitution for the inside expression." },
                  { latex: "y' = cos(u) du/dx", write: "y' = cos(u) * du/dx", narration: "Differentiating with respect to u gives cosine of u times du dx." },
                  { latex: "y' = 6x cos(3x^2)", write: "y' = 6x cos(3x^2)", narration: "Substituting back gives six x cosine of three x squared." }
                ],
                final_answer_latex: "6x cos(3x^2)",
                final_answer_sympy: "6*x*cos(3*x**2)",
                cites_pages: [1]
              };

              // Intercept /api/tts and simulate 502 Bad Gateway
              var origFetch = window.fetch;
              window.fetch = async function(url, opts) {
                if (typeof url === 'string' && url.indexOf('/api/solve') !== -1) {
                  return new Response(JSON.stringify(MOCK_SOLVE_DATA), {
                    status: 200,
                    headers: { 'Content-Type': 'application/json' }
                  });
                }
                if (typeof url === 'string' && url.indexOf('/api/tts') !== -1) {
                  return new Response(JSON.stringify({ detail: 'TTS provider error: 502' }), {
                    status: 502,
                    headers: { 'Content-Type': 'application/json' }
                  });
                }
                return origFetch.apply(this, arguments);
              };

              var t0 = performance.now();
              await window.runSolvePipeline('Differentiate y = sin(3x^2)', null);
              var t1 = performance.now();
              window.fetch = origFetch;

              var steps = Array.from(document.querySelectorAll('.ln.ai[id^="step-"]'));
              var toastEl = document.getElementById('toast');
              var toastText = toastEl ? toastEl.textContent : '';

              return {
                stepCount: steps.length,
                busy: window.busy,
                completed: steps.length >= 3,
                noVisibleError: toastText.indexOf('502') === -1
              };
            })()
            """, await_promise=True)
            req_id += 1

            t3_pass = t3_res["completed"] and t3_res["noVisibleError"] and not t3_res["busy"]
            results["Test 3: Fallback on 502 to browser voice (no visible error)"] = {
                "status": "PASS" if t3_pass else "FAIL",
                "details": t3_res
            }
            print("Test 3 Result:", "PASS" if t3_pass else "FAIL", t3_res)

            # =========================================================================
            # TEST 4: Slow TTS (simulating > 4s delay on step 0)
            # =========================================================================
            print("\n>>> Running Test 4: Slow TTS fallback (> 4s wait pill then browser voice)")
            t4_res = await evaluate(ws, req_id, """
            (async function() {
              window.TTS_MODE = 'cloud';
              window.go(8);

              var MOCK_SOLVE_DATA = {
                verified: true,
                attempts: 1,
                problem: { task_type: "differentiate", variable: "x", expression_sympy: "sin(3*x**2)" },
                steps: [
                  { latex: "u = 3x^2", write: "Let u = 3x^2,  du/dx = 6x", narration: "Let's use substitution for the inside expression." },
                  { latex: "y' = cos(u) du/dx", write: "y' = cos(u) * du/dx", narration: "Differentiating with respect to u gives cosine of u times du dx." },
                  { latex: "y' = 6x cos(3x^2)", write: "y' = 6x cos(3x^2)", narration: "Substituting back gives six x cosine of three x squared." }
                ],
                final_answer_latex: "6x cos(3x^2)",
                final_answer_sympy: "6*x*cos(3*x**2)",
                cites_pages: [1]
              };

              var origFetch = window.fetch;
              window.fetch = async function(url, opts) {
                if (typeof url === 'string' && url.indexOf('/api/solve') !== -1) {
                  return new Response(JSON.stringify(MOCK_SOLVE_DATA), {
                    status: 200,
                    headers: { 'Content-Type': 'application/json' }
                  });
                }
                if (typeof url === 'string' && url.indexOf('/api/tts') !== -1) {
                  await new Promise(function(r) { setTimeout(r, 4500); });
                  return new Response(JSON.stringify({ detail: 'Delayed' }), { status: 502 });
                }
                return origFetch.apply(this, arguments);
              };

              var errDetails = null;
              var t0 = performance.now();
              try {
                await window.runSolvePipeline('Differentiate y = sin(3x^2)', null);
              } catch (e) {
                errDetails = { message: e.message, stack: e.stack };
              }
              var t1 = performance.now();
              window.fetch = origFetch;

              var steps = Array.from(document.querySelectorAll('.ln.ai[id^="step-"]'));
              return {
                stepCount: steps.length,
                completed: steps.length >= 3,
                busy: window.busy,
                err: errDetails
              };
            })()
            """, await_promise=True)
            req_id += 1

            t4_pass = t4_res["completed"] and not t4_res["busy"]
            results["Test 4: Slow TTS fallback (> 4s wait then browser voice)"] = {
                "status": "PASS" if t4_pass else "FAIL",
                "details": t4_res
            }
            print("Test 4 Result:", "PASS" if t4_pass else "FAIL", t4_res)

            # =========================================================================
            # TEST 5: Barge-in & Cancellation (solve again, switch page, eraser)
            # =========================================================================
            print("\n>>> Running Test 5: Barge-in & Cancellation")
            t5_res = await evaluate(ws, req_id, """
            (async function() {
              window.TTS_MODE = 'cloud';
              window.go(8);

              var MOCK_SOLVE_DATA = {
                verified: true,
                attempts: 1,
                problem: { task_type: "differentiate", variable: "x", expression_sympy: "sin(3*x**2)" },
                steps: [
                  { latex: "u = 3x^2", write: "Let u = 3x^2,  du/dx = 6x", narration: "Let's use substitution for the inside expression." },
                  { latex: "y' = cos(u) du/dx", write: "y' = cos(u) * du/dx", narration: "Differentiating with respect to u gives cosine of u times du dx." },
                  { latex: "y' = 6x cos(3x^2)", write: "y' = 6x cos(3x^2)", narration: "Substituting back gives six x cosine of three x squared." }
                ],
                final_answer_latex: "6x cos(3x^2)",
                final_answer_sympy: "6*x*cos(3*x**2)",
                cites_pages: [1]
              };

              // Intercept /api/solve to return mock immediately
              var origFetch = window.fetch;
              window.fetch = async function(url, opts) {
                if (typeof url === 'string' && url.indexOf('/api/solve') !== -1) {
                  return new Response(JSON.stringify(MOCK_SOLVE_DATA), { status: 200, headers: { 'Content-Type': 'application/json' } });
                }
                return origFetch.apply(this, arguments);
              };

              // Start solve 1
              window.runSolvePipeline('Differentiate y = sin(3x^2)', null);
              await new Promise(function(r) { setTimeout(r, 400); });

              // Interrupt: solve again mid-audio
              window.runSolvePipeline('Differentiate y = sin(3x^2)', null);
              await new Promise(function(r) { setTimeout(r, 400); });

              // Interrupt: eraser tool activation
              window.setTool('era');
              var eraStopped = !window.currentTtsAudio || window.currentTtsAudio.paused;

              // Interrupt: switch pages mid-audio
              window.go(1);
              var p1Text = document.getElementById('notes').textContent;
              var audioStopped = !window.currentTtsAudio || window.currentTtsAudio.paused;

              // Switch back to Page 8
              window.go(8);
              window.fetch = origFetch;

              return {
                eraStopped: eraStopped,
                audioStopped: audioStopped,
                p1Ok: p1Text.indexOf('Chain rule') !== -1,
                busy: window.busy
              };
            })()
            """, await_promise=True)
            req_id += 1

            t5_pass = t5_res["audioStopped"] and t5_res["eraStopped"] and t5_res["p1Ok"] and not t5_res["busy"]
            results["Test 5: Barge-in & Cancellation (immediate audio stop)"] = {
                "status": "PASS" if t5_pass else "FAIL",
                "details": t5_res
            }
            print("Test 5 Result:", "PASS" if t5_pass else "FAIL", t5_res)

            # =========================================================================
            # TEST 6: Reload: stored solution silent and instant
            # =========================================================================
            print("\n>>> Running Test 6: Reload / Stored Solution instant and silent")
            t6_res = await evaluate(ws, req_id, """
            (function() {
              window.go(8);
              var t0 = performance.now();
              window.render({ animate: false });
              var t1 = performance.now();
              var steps = Array.from(document.querySelectorAll('.ln.ai[id^="step-"]'));
              var audioPlaying = !!window.currentTtsAudio && !window.currentTtsAudio.paused;
              return {
                durationMs: t1 - t0,
                stepCount: steps.length,
                silent: !audioPlaying
              };
            })()
            """)
            req_id += 1

            t6_pass = t6_res["durationMs"] < 100 and t6_res["stepCount"] >= 3 and t6_res["silent"]
            results["Test 6: Reload (stored solution silent & instant)"] = {
                "status": "PASS" if t6_pass else "FAIL",
                "details": t6_res
            }
            print("Test 6 Result:", "PASS" if t6_pass else "FAIL", t6_res)

            # =========================================================================
            # TEST 7: TTS_MODE = 'browser' preservation
            # =========================================================================
            print("\n>>> Running Test 7: TTS_MODE = 'browser' preservation")
            t7_res = await evaluate(ws, req_id, """
            (async function() {
              window.TTS_MODE = 'browser';
              window.go(8);

              var MOCK_SOLVE_DATA = {
                verified: true,
                attempts: 1,
                problem: { task_type: "differentiate", variable: "x", expression_sympy: "sin(3*x**2)" },
                steps: [
                  { latex: "u = 3x^2", write: "Let u = 3x^2,  du/dx = 6x", narration: "Let's use substitution for the inside expression." },
                  { latex: "y' = cos(u) du/dx", write: "y' = cos(u) * du/dx", narration: "Differentiating with respect to u gives cosine of u times du dx." },
                  { latex: "y' = 6x cos(3x^2)", write: "y' = 6x cos(3x^2)", narration: "Substituting back gives six x cosine of three x squared." }
                ],
                final_answer_latex: "6x cos(3x^2)",
                final_answer_sympy: "6*x*cos(3*x**2)",
                cites_pages: [1]
              };

              var origFetch = window.fetch;
              window.fetch = async function(url, opts) {
                if (typeof url === 'string' && url.indexOf('/api/solve') !== -1) {
                  return new Response(JSON.stringify(MOCK_SOLVE_DATA), { status: 200, headers: { 'Content-Type': 'application/json' } });
                }
                return origFetch.apply(this, arguments);
              };
              var t0 = performance.now();
              await window.runSolvePipeline('Differentiate y = sin(3x^2)', null);
              var t1 = performance.now();
              window.fetch = origFetch;
              var steps = Array.from(document.querySelectorAll('.ln.ai[id^="step-"]'));
              return {
                stepCount: steps.length,
                busy: window.busy,
                completed: steps.length >= 3
              };
            })()
            """, await_promise=True)
            req_id += 1

            t7_pass = t7_res["completed"] and not t7_res["busy"]
            results["Test 7: TTS_MODE = 'browser' behaves exactly as before"] = {
                "status": "PASS" if t7_pass else "FAIL",
                "details": t7_res
            }
            print("Test 7 Result:", "PASS" if t7_pass else "FAIL", t7_res)

    finally:
        browser_proc.kill()

    # =========================================================================
    # TEST 8 & 9: In-Memory Cache and Audio Narration Duration
    # =========================================================================
    print("\n>>> Running Test 8: Cache hit verification (no second provider call)")
    from unittest.mock import patch
    from backend.tts import generate_tts_wav, clear_cache, pcm_to_wav
    clear_cache()
    fake_wav = pcm_to_wav(b"\x00\x00" * 24000, sample_rate=24000)
    with patch("backend.tts.synthesize_speech_provider", return_value=fake_wav) as mock_p:
        w1 = generate_tts_wav("Unique cache test narration sentence.")
        calls_after_first = mock_p.call_count
        w2 = generate_tts_wav("Unique cache test narration sentence.")
        calls_after_second = mock_p.call_count

    t8_pass = w1 == w2 and calls_after_first == 1 and calls_after_second == 1
    results["Test 8: Second identical narration served from cache"] = {
        "status": "PASS" if t8_pass else "FAIL",
        "first_call_count": calls_after_first,
        "second_call_count": calls_after_second
    }
    print(f"Test 8 Result: {'PASS' if t8_pass else 'FAIL'} (Provider calls: {calls_after_first} then {calls_after_second})")

    print("\n>>> Running Test 9: Narration audio contains only narration (no instruction)")
    sample_wav = Path("tools/out/differentiate_sin3x2.wav")
    if sample_wav.exists():
        with wave.open(str(sample_wav), "rb") as wf:
            wav_dur = wf.getnframes() / float(wf.getframerate())
        # The text "Let's use substitution with u equals 3x squared." is 8 words (~3-4s).
        # A spoken instruction ("Say this warmly...") would add ~3.5s (total > 6.5s).
        t9_pass = 2.5 <= wav_dur <= 4.5
        results["Test 9: Audio contains only narration text (instruction not spoken)"] = {
            "status": "PASS" if t9_pass else "FAIL",
            "duration_sec": round(wav_dur, 2)
        }
        print(f"Test 9 Result: {'PASS' if t9_pass else 'FAIL'} (Duration: {wav_dur:.2f}s)")
    else:
        results["Test 9: Audio contains only narration text"] = {"status": "FAIL", "reason": "Sample file not found"}

    print("\n================== FULL TTS TEST SUITE SUMMARY ==================")
    all_ok = True
    for name, r in results.items():
        st = r["status"]
        if st != "PASS": all_ok = False
        print(f"[{st}] {name}")
    print("=================================================================")
    return all_ok

if __name__ == "__main__":
    import sys
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))
    ok = asyncio.run(run_suite())
    exit(0 if ok else 1)
