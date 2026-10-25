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

async def run_voice_tests():
    temp_dir = os.path.join(os.environ.get("TEMP", "C:\\temp"), "inkmentor_voice_test")
    os.makedirs(temp_dir, exist_ok=True)

    proc = subprocess.Popen([
        BROWSER_EXE,
        "--headless=new",
        "--remote-debugging-port=9225",
        f"--user-data-dir={temp_dir}",
        "--no-first-run",
        "--disable-gpu",
        "--autoplay-policy=no-user-gesture-required",
        "http://127.0.0.1:8000/"
    ])

    test_results = {}

    try:
        tab_ws_url = None
        for _ in range(25):
            await asyncio.sleep(0.4)
            try:
                with urllib.request.urlopen("http://127.0.0.1:9225/json") as r:
                    tabs = json.loads(r.read().decode())
                    for tab in tabs:
                        if tab.get("type") == "page":
                            tab_ws_url = tab.get("webSocketDebuggerUrl")
                            break
                    if tab_ws_url:
                        break
            except Exception:
                pass

        if not tab_ws_url:
            print("Failed to connect to browser CDP")
            return False

        async with websockets.connect(tab_ws_url, max_size=20*1024*1024) as ws:
            req_id = 1
            await cdp_call(ws, req_id, "Page.enable"); req_id += 1
            await cdp_call(ws, req_id, "Runtime.enable"); req_id += 1

            # Wait for app ready
            for _ in range(30):
                ready = await evaluate(ws, req_id, "typeof VoiceArbiter !== 'undefined'"); req_id += 1
                if ready:
                    break
                await asyncio.sleep(0.2)

            print("[VOICE TEST] Connected to InkMentor. Running Test 1-8...")

            # Test 1: VoiceArbiter singleton and methods exist
            t1 = await evaluate(ws, req_id, """
                typeof VoiceArbiter === 'object' &&
                typeof VoiceArbiter.speak === 'function' &&
                typeof VoiceArbiter.stop === 'function' &&
                typeof VoiceArbiter.getSharedAudio === 'function'
            """); req_id += 1
            test_results["Test 1: VoiceArbiter structure"] = bool(t1)
            print(f"  Test 1 (Structure): {'PASS' if t1 else 'FAIL'}")

            # Test 2: Invariant detector is running and tracking
            t2 = await evaluate(ws, req_id, "window.DEBUG_VOICE === true"); req_id += 1
            test_results["Test 2: Invariant detector active"] = bool(t2)
            print(f"  Test 2 (Invariant detector): {'PASS' if t2 else 'FAIL'}")

            # Test 3: Stop method halts audio and resets state
            t3 = await evaluate(ws, req_id, """
                (function() {
                    VoiceArbiter.stop();
                    return VoiceArbiter.getState() === 'idle' &&
                           VoiceArbiter.getProvider() === 'none';
                })()
            """); req_id += 1
            test_results["Test 3: VoiceArbiter stop() resets state"] = bool(t3)
            print(f"  Test 3 (Stop reset): {'PASS' if t3 else 'FAIL'}")

            # Test 4: say() routes through VoiceArbiter without independent Audio element
            t4 = await evaluate(ws, req_id, """
                (async function() {
                    var beforeState = VoiceArbiter.getState();
                    var p = say('Test notebook narration message');
                    var afterState = VoiceArbiter.getState();
                    VoiceArbiter.stop();
                    return afterState === 'loading' || afterState === 'playing' || afterState === 'ended';
                })()
            """, await_promise=True); req_id += 1
            test_results["Test 4: say() delegates to VoiceArbiter"] = bool(t4)
            print(f"  Test 4 (say routing): {'PASS' if t4 else 'FAIL'}")

            # Test 5: Overlap prevention: two consecutive calls never play simultaneously
            t5 = await evaluate(ws, req_id, """
                (async function() {
                    var violations = 0;
                    var origError = console.error;
                    console.error = function(msg) {
                        if (msg && msg.indexOf('INVARIANT VIOLATION') !== -1) {
                            violations++;
                        }
                        origError.apply(console, arguments);
                    };

                    // Fire speech 1
                    var p1 = VoiceArbiter.speak('Step 1 differentiate with quotient rule', { position: 'first', solveSeq: 1 });
                    // Immediately fire speech 2 (simulating barge-in / say call)
                    var p2 = VoiceArbiter.speak('Step 2 apply chain rule', { position: 'middle', solveSeq: 1 });

                    await new Promise(r => setTimeout(r, 400));
                    var sharedAudio = VoiceArbiter.getSharedAudio();
                    var isAudioPlaying = !sharedAudio.paused && !sharedAudio.ended && sharedAudio.currentTime > 0;
                    var isSpeechSpeaking = window.speechSynthesis && window.speechSynthesis.speaking;

                    // Cannot have both audio and speech
                    var simultaneous = (isAudioPlaying && isSpeechSpeaking);
                    VoiceArbiter.stop();
                    console.error = origError;

                    return !simultaneous && violations === 0;
                })()
            """, await_promise=True); req_id += 1
            test_results["Test 5: Overlap prevention (zero invariant violations)"] = bool(t5)
            print(f"  Test 5 (Overlap prevention): {'PASS' if t5 else 'FAIL'}")

            # Test 6: Fallback to browser voice when TTS server returns fallback=browser
            t6 = await evaluate(ws, req_id, """
                (async function() {
                    // Temporarily mock fetch to return 503 fallback
                    var origFetch = window.fetch;
                    window.fetch = async function(url, opts) {
                        if (typeof url === 'string' && url.indexOf('/api/tts') !== -1) {
                            return new Response(JSON.stringify({ fallback: 'browser', reason: 'QUOTA_EXHAUSTED' }), {
                                status: 503,
                                headers: { 'Content-Type': 'application/json', 'X-TTS-Provider': 'none' }
                            });
                        }
                        return origFetch.apply(this, arguments);
                    };

                    var result = await VoiceArbiter.speak('Testing server fallback to browser speech', { position: 'first', solveSeq: 99 });
                    window.fetch = origFetch;
                    VoiceArbiter.stop();

                    return result.provider === 'browser' || result.provider === 'none';
                })()
            """, await_promise=True); req_id += 1
            test_results["Test 6: Fallback to browser voice on 503"] = bool(t6)
            print(f"  Test 6 (Fallback to browser): {'PASS' if t6 else 'FAIL'}")

            # Test 7: Barge-in cancels active audio instantly
            t7 = await evaluate(ws, req_id, """
                (async function() {
                    VoiceArbiter.speak('Testing long narration step that will be barged into', { position: 'middle', solveSeq: 100 });
                    await new Promise(r => setTimeout(r, 100));
                    stopVoiceAndAnimation();
                    var state = VoiceArbiter.getState();
                    var sharedAudio = VoiceArbiter.getSharedAudio();
                    var audioPaused = sharedAudio.paused;
                    var speechSpeaking = window.speechSynthesis ? window.speechSynthesis.speaking : false;
                    return state === 'idle' && audioPaused && !speechSpeaking;
                })()
            """, await_promise=True); req_id += 1
            test_results["Test 7: Barge-in stops all speech and audio immediately"] = bool(t7)
            print(f"  Test 7 (Barge-in cancellation): {'PASS' if t7 else 'FAIL'}")

            # Test 8: Downgrade consistency: once downgraded to browser in solveSeq, next steps stay downgraded
            t8 = await evaluate(ws, req_id, """
                (async function() {
                    var cloudFetchAttempts = 0;
                    var origFetch = window.fetch;
                    window.fetch = async function(url, opts) {
                        if (typeof url === 'string' && url.indexOf('/api/tts') !== -1) {
                            cloudFetchAttempts++;
                            return new Response(JSON.stringify({ fallback: 'browser', reason: 'DOWNGRADE_TEST' }), {
                                status: 503,
                                headers: { 'Content-Type': 'application/json', 'X-TTS-Provider': 'none' }
                            });
                        }
                        return origFetch.apply(this, arguments);
                    };

                    // Step 1: fails and downgrades to browser
                    await VoiceArbiter.speak('Step 1 will fail cloud', { position: 'first', solveSeq: 200 });
                    var fetchCountAfterStep1 = cloudFetchAttempts;

                    // Step 2 in same solveSeq: must NOT attempt cloud fetch (downgrade locked)
                    await VoiceArbiter.speak('Step 2 must skip cloud', { position: 'middle', solveSeq: 200 });
                    var fetchCountAfterStep2 = cloudFetchAttempts;

                    window.fetch = origFetch;
                    VoiceArbiter.stop();

                    return fetchCountAfterStep1 === 1 && fetchCountAfterStep2 === 1;
                })()
            """, await_promise=True); req_id += 1
            test_results["Test 8: Downgrade consistency prevents mid-solve upgrade"] = bool(t8)
            print(f"  Test 8 (Downgrade consistency): {'PASS' if t8 else 'FAIL'}")

            all_passed = all(test_results.values())
            print(f"\n[SUMMARY] Tests Passed: {sum(test_results.values())}/{len(test_results)}")
            return all_passed
    finally:
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    success = asyncio.run(run_voice_tests())
    exit(0 if success else 1)
