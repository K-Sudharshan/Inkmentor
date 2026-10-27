import asyncio
import io
import json
import os
import sys
import subprocess
import time
import urllib.request
import wave
import websockets
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath("."))
load_dotenv("backend/.env")

EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BROWSER_EXE = EDGE_EXE if os.path.exists(EDGE_EXE) else CHROME_EXE
BASE_URL = "http://127.0.0.1:8000"

results = {}

def test_1_gemini_tts_live_endpoint():
    print("\n--- Test 1: Live Gemini TTS API Endpoint ---")
    url = f"{BASE_URL}/api/tts"
    text = "First, integrate with respect to x from 0 to 1."
    payload = {"text": text, "voice": "Puck", "position": "first"}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            dur = round((time.time() - t0) * 1000, 2)
            content_type = resp.headers.get("Content-Type")
            provider = resp.headers.get("X-TTS-Provider")
            audio_bytes = resp.read()

            with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
                channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                framerate = wf.getframerate()
                nframes = wf.getnframes()
                audio_dur = round(nframes / framerate, 2)

            print(f"Status: {resp.status}")
            print(f"Latency: {dur} ms")
            print(f"Provider: {provider}")
            print(f"Audio Format: {framerate}Hz, {channels}ch, {sampwidth*8}-bit PCM")
            print(f"Audio Duration: {audio_dur}s, Payload: {len(audio_bytes)} bytes")

            ok = (
                resp.status == 200 and
                content_type == "audio/wav" and
                provider in ("gemini", "cache") and
                framerate == 24000 and
                channels == 1 and
                len(audio_bytes) > 20000
            )
            results["Test 1: Gemini TTS Live Endpoint"] = ok
            print(f"Result: {'PASS' if ok else 'FAIL'}")
    except Exception as e:
        print(f"Test 1 Failed: {e}")
        results["Test 1: Gemini TTS Live Endpoint"] = False

def test_2_cache_performance_boost():
    print("\n--- Test 2: Audio Cache Performance Boost ---")
    url = f"{BASE_URL}/api/tts"
    text = "First, integrate with respect to x from 0 to 1."
    payload = {"text": text, "voice": "Puck", "position": "first"}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            dur = round((time.time() - t0) * 1000, 2)
            provider = resp.headers.get("X-TTS-Provider")
            print(f"Cache Hit Latency: {dur} ms")
            print(f"Provider Header: {provider}")
            ok = resp.status == 200 and dur < 100 and provider == "cache"
            results["Test 2: Cache Performance Boost (<100ms)"] = ok
            print(f"Result: {'PASS' if ok else 'FAIL'}")
    except Exception as e:
        print(f"Test 2 Failed: {e}")
        results["Test 2: Cache Performance Boost (<100ms)"] = False

def test_3_groq_chunking_and_vocal_direction():
    print("\n--- Test 3: Groq Chunking & Direction Logic ---")
    from backend.tts import chunk_text_with_direction, validate_direction, GROQ_TTS_CHAR_LIMIT
    long_text = (
        "Let's carefully compute the partial derivative of this function with respect to x first, "
        "treating every y variable as a constant throughout the entire calculation, "
        "and then we will evaluate the boundary limits at the final step."
    )
    chunks = chunk_text_with_direction(long_text, direction="whisper", limit=120)
    print(f"Original length: {len(long_text)} chars -> Split into {len(chunks)} chunks:")
    all_within_limit = True
    for idx, c in enumerate(chunks, 1):
        print(f"  Chunk {idx} ({len(c)} chars): {c}")
        if len(c) > 120 or not c.startswith("[whisper] "):
            all_within_limit = False

    ok = all_within_limit and len(chunks) >= 2
    results["Test 3: Groq Chunking & Direction Injection"] = ok
    print(f"Result: {'PASS' if ok else 'FAIL'}")

def test_4_browser_fallback_payload():
    print("\n--- Test 4: Provider Exhaustion -> 503 Browser Fallback ---")
    from backend.tts import TTSAllProvidersFailed
    from fastapi.testclient import TestClient
    from unittest.mock import patch
    from backend.main import app

    client = TestClient(app)
    with patch("backend.tts.synthesize_speech_gemini", side_effect=RuntimeError("GEMINI_DOWN")):
        with patch("backend.tts.synthesize_speech_groq", side_effect=RuntimeError("GROQ_DOWN")):
            resp = client.post("/api/tts", json={"text": "A completely unseen sentence for fallback testing."})
            print(f"Status Code: {resp.status_code}")
            print(f"Headers: X-TTS-Provider={resp.headers.get('x-tts-provider')}")
            body = resp.json()
            print(f"Response Body: {body}")
            ok = (
                resp.status_code == 503 and
                body.get("fallback") == "browser" and
                resp.headers.get("x-tts-provider") == "none"
            )
            results["Test 4: Browser Fallback Contract (503 fallback=browser)"] = ok
            print(f"Result: {'PASS' if ok else 'FAIL'}")

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
    return res.get("result", {}).get("result", {}).get("value")

async def test_5_browser_e2e_audio_layer():
    print("\n--- Test 5: Browser E2E Audio Arbiter & Invariant Check ---")
    temp_dir = os.path.join(os.environ.get("TEMP", "C:\\temp"), f"ink_audio_e2e_{int(time.time())}")
    os.makedirs(temp_dir, exist_ok=True)

    proc = subprocess.Popen([
        BROWSER_EXE,
        "--headless=new",
        "--remote-debugging-port=9227",
        f"--user-data-dir={temp_dir}",
        "--no-first-run",
        "--disable-gpu",
        "--autoplay-policy=no-user-gesture-required",
        f"{BASE_URL}/"
    ])

    try:
        tab_ws = None
        for _ in range(30):
            await asyncio.sleep(0.3)
            try:
                with urllib.request.urlopen("http://127.0.0.1:9227/json", timeout=2) as r:
                    tabs = json.loads(r.read().decode())
                    for t in tabs:
                        if t.get("type") == "page":
                            tab_ws = t.get("webSocketDebuggerUrl")
                            break
                    if tab_ws:
                        break
            except Exception:
                pass

        if not tab_ws:
            print("ERROR: Failed to connect to CDP")
            results["Test 5: Browser E2E Audio Arbiter & Invariant Check"] = False
            return

        async with websockets.connect(tab_ws, max_size=20_000_000) as ws:
            req_id = 1
            await cdp_call(ws, req_id, "Page.enable"); req_id += 1
            await cdp_call(ws, req_id, "Runtime.enable"); req_id += 1
            await cdp_call(ws, req_id, "Page.navigate", {"url": f"{BASE_URL}/"}); req_id += 1

            # Wait for VoiceArbiter
            for _ in range(50):
                await asyncio.sleep(0.2)
                ready = await evaluate(ws, req_id, "typeof VoiceArbiter !== 'undefined'"); req_id += 1
                if ready is True:
                    break

            # Run Invariant & Preload verification
            eval_test = """
            (async function() {
                // 1. Check VoiceArbiter initialization
                if (!VoiceArbiter || typeof VoiceArbiter.speak !== 'function') return { ok: false, err: 'No VoiceArbiter' };

                // 2. Test Cloud Audio Playback
                var res1 = await VoiceArbiter.speak('Evaluating the inner integral.', { position: 'first', solveSeq: 10 });

                // 3. Test immediate stop / barge-in
                var speakP2 = VoiceArbiter.speak('This will be interrupted immediately.', { position: 'middle', solveSeq: 10 });
                await new Promise(r => setTimeout(r, 50));
                VoiceArbiter.stop();
                var stateAfterStop = VoiceArbiter.getState();
                var audio = VoiceArbiter.getSharedAudio();
                var paused = audio ? audio.paused : true;

                // 4. Test Browser Native Fallback
                var origFetch = window.fetch;
                window.fetch = async function(url) {
                    if (url.indexOf('/api/tts') !== -1) {
                        return new Response(JSON.stringify({ fallback: 'browser', reason: 'TEST' }), { status: 503, headers: { 'Content-Type': 'application/json' } });
                    }
                    return origFetch.apply(this, arguments);
                };

                var fallbackResult = await VoiceArbiter.speak('Falling back to browser speech synthesis.', { position: 'middle', solveSeq: 11 });
                window.fetch = origFetch;
                VoiceArbiter.stop();

                return {
                    ok: true,
                    cloudProvider: res1.provider,
                    cloudDuration: res1.durationMs,
                    stopState: stateAfterStop,
                    audioPaused: paused,
                    fallbackProvider: fallbackResult.provider
                };
            })()
            """
            val = await evaluate(ws, req_id, eval_test, await_promise=True); req_id += 1
            print(f"Browser Audio Verification Results: {val}")

            ok = isinstance(val, dict) and (
                val.get("ok") is True and
                val.get("cloudProvider") in ("gemini", "groq", "cache", "browser", "none") and
                val.get("stopState") == "idle" and
                val.get("audioPaused") is True and
                val.get("fallbackProvider") in ("browser", "none")
            )
            results["Test 5: Browser E2E Audio Arbiter & Invariant Check"] = ok
            print(f"Result: {'PASS' if ok else 'FAIL'}")

    finally:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            pass

def main():
    print("=" * 60)
    print("COMPREHENSIVE AUDIO LAYER TEST SUITE")
    print("=" * 60)

    test_1_gemini_tts_live_endpoint()
    test_2_cache_performance_boost()
    test_3_groq_chunking_and_vocal_direction()
    test_4_browser_fallback_payload()
    asyncio.run(test_5_browser_e2e_audio_layer())

    print("\n" + "=" * 60)
    print("AUDIO LAYER TEST SUMMARY")
    print("=" * 60)
    all_ok = True
    for name, status in results.items():
        print(f"  {name:50s}: {'[ PASS ]' if status else '[ FAIL ]'}")
        if not status:
            all_ok = False
    print(f"\nFinal Result: {'ALL TESTS PASSED!' if all_ok else 'SOME TESTS FAILED'}")
    return all_ok

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
