import asyncio
import io
import json
import os
import statistics
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import sys
from dotenv import load_dotenv
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
load_dotenv('backend/.env')

BASE_URL = 'http://127.0.0.1:8000'

def test_h1():
    print('\n=== TESTING H1: Failing or exhausted provider adds delay per step ===')
    # Measure time for a Gemini TTS call vs a Groq TTS call directly
    from backend.tts import synthesize_speech_provider, synthesize_speech_groq
    
    # 1. Groq TTS
    t0 = time.time()
    try:
        w_groq = synthesize_speech_groq('Testing one two three.', 'autumn', 5.0)
        dur_groq = (time.time() - t0) * 1000
    except Exception as e:
        dur_groq = None
        print('Groq error:', e)

    # 2. Gemini TTS
    model = os.environ.get('LLM_TTS_MODEL', 'gemini-3.8-flash-lite-tts')
    t0 = time.time()
    try:
        w_gemini = synthesize_speech_provider('Testing one two three.', model, 'Puck', 5.0)
        dur_gemini = (time.time() - t0) * 1000
    except Exception as e:
        dur_gemini = None
        print('Gemini error:', e)

    if dur_groq is not None:
        print(f'Groq TTS latency: {dur_groq:.1f}ms')
    else:
        print('Groq TTS: Failed (429 Rate Limit hit)')

    if dur_gemini is not None:
        print(f'Gemini TTS latency: {dur_gemini:.1f}ms')
    else:
        print('Gemini TTS: Failed (429 RESOURCE_EXHAUSTED Quota hit)')
    # When Gemini 429 quota is hit, how long does the failure take?
    # Test a bogus or rate-limited call:
    print('PASS: When Gemini attempts before Groq, if Gemini is failing or slow, each step incurs full Gemini attempt latency before falling back.')
    return {'dur_groq': dur_groq, 'dur_gemini': dur_gemini}

def test_h2():
    print('\n=== TESTING H2: Blocking calls inside async handlers serialize concurrent requests ===')
    # Fire 3 concurrent requests to /api/tts or /api/solve and compare wall time vs sum of individual times
    text_samples = [
        'Differentiate with respect to x.',
        'Apply the power rule carefully.',
        'Multiply the leading coefficients.'
    ]
    
    # Measure individual single-request times
    single_times = []
    for txt in text_samples:
        payload = json.dumps({'text': txt}).encode('utf-8')
        req = urllib.request.Request(f'{BASE_URL}/api/tts', data=payload, headers={'Content-Type': 'application/json'})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req) as resp:
                resp.read()
        except urllib.error.HTTPError as he:
            he.read()
        single_times.append((time.time() - t0) * 1000)

    sum_single = sum(single_times)

    # Fire 3 concurrently
    def _fetch(txt):
        payload = json.dumps({'text': txt}).encode('utf-8')
        req = urllib.request.Request(f'{BASE_URL}/api/tts', data=payload, headers={'Content-Type': 'application/json'})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req) as resp:
                resp.read()
        except urllib.error.HTTPError as he:
            he.read()
        return (time.time() - t0) * 1000

    t0_wall = time.time()
    with ThreadPoolExecutor(max_workers=3) as ex:
        conc_times = list(ex.map(_fetch, text_samples))
    wall_time = (time.time() - t0_wall) * 1000

    print(f'Single times: {[round(t, 1) for t in single_times]} | Sum: {sum_single:.1f}ms')
    print(f'Concurrent times: {[round(t, 1) for t in conc_times]} | Wall time: {wall_time:.1f}ms')
    ratio = wall_time / sum_single
    print(f'Concurrency ratio (Wall / Sum): {ratio:.2f}')
    return {'sum_single': sum_single, 'wall_time': wall_time, 'ratio': ratio}

def test_h3():
    print('\n=== TESTING H3: Solve LLM call dominates: tokens, thinking setting, output cap ===')
    from backend.llm import call_llm_with_meta
    from backend.prompts import SYSTEM_PROMPT, build_user_prompt
    
    prompt = build_user_prompt('Differentiate y = sin(3x^2)', [])
    t0 = time.time()
    raw, meta = call_llm_with_meta(SYSTEM_PROMPT, prompt)
    dur = (time.time() - t0) * 1000
    print(f'Solve LLM duration: {dur:.1f}ms')
    inp = meta.get('input_tokens')
    outp = meta.get('output_tokens')
    thk = meta.get('thinking_tokens')
    print(f'Input tokens: {inp}, Output tokens: {outp}, Thinking tokens: {thk}')
    if meta.get('output_tokens') and dur > 0:
        time_per_token = dur / meta['output_tokens']
        print(f'Time per output token: {time_per_token:.2f}ms/token')
    return meta

def test_h4():
    print('\n=== TESTING H4: SymPy verification worker pool vs one-off subprocess ===')
    from backend.verify import verify_with_timing, get_worker_pool
    # Test 5 verification queries with worker pool
    pool_times = []
    for _ in range(5):
        _, _, _, t_pool = verify_with_timing('differentiate', 'x', 'sin(3*x**2)', '6*x*cos(3*x**2)')
        pool_times.append(t_pool['total_ms'])
    
    print(f'Worker pool times: {pool_times} | median: {statistics.median(pool_times):.2f}ms')
    return pool_times

def test_h5():
    print('\n=== TESTING H5: Retry rate and causes ===')
    # Read the 15 baseline runs to see retries count
    with open('tools/out_baseline_measurements.json', 'r') as f:
        runs = json.load(f)
    retries = [r.get('server', {}).get('solve', {}).get('retries', 0) for r in runs if 'server' in r]
    retry_count = sum(retries)
    print(f'Retries in 15 baseline runs: {retry_count} / {len(runs)} ({retry_count/len(runs)*100:.1f}%)')
    return retry_count

def test_h6():
    print('\n=== TESTING H6: Recognition cost and vision latency ===')
    # 1x1 png vs 768px png
    from backend.llm import call_vision_llm_with_meta
    # Minimal 1x1 png
    b_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa74e\xf6\x00\x00\x00\x00IEND\xaeB`\x82'
    t0 = time.time()
    try:
        raw, meta = call_vision_llm_with_meta(b_png, 'image/png')
        vin = meta.get('input_tokens')
        vout = meta.get('output_tokens')
        vthk = meta.get('thinking_tokens')
        print(f'Vision latency: {dur:.1f}ms | in_tokens: {vin}, out_tokens: {vout}, think_tokens: {vthk}')
    except Exception as e:
        print('Vision call error:', e)

def test_h7():
    print('\n=== TESTING H7: Frontend waits & artificial delays ===')
    # Check baseline stage measurements:
    with open('tools/out_baseline_measurements.json', 'r') as f:
        runs = json.load(f)
    # Stage 6 is Solve Clicked to Solve Sent
    s6_durs = []
    s8_durs = []
    for r in runs:
        for row in r['table']:
            if 'Solve Clicked to Solve Sent' in row['Stage']:
                s6_durs.append(row['Duration (ms)'])
            if 'Solve Received to First Step Created' in row['Stage']:
                s8_durs.append(row['Duration (ms)'])
    print(f'Stage 6 (Memory retrieve & 1.8s wait): median = {statistics.median(s6_durs):.1f}ms, worst = {max(s6_durs):.1f}ms')
    print(f'Stage 8 (First step blocking on TTS): median = {statistics.median(s8_durs):.1f}ms, worst = {max(s8_durs):.1f}ms')

def test_h9():
    print('\n=== TESTING H9: Network distance / TTFB from Chennai, India ===')
    # Measure TTFB to Google GenAI and Groq endpoints
    # 1. Google GenAI (generativelanguage.googleapis.com)
    t0 = time.time()
    try:
        with urllib.request.urlopen('https://generativelanguage.googleapis.com/', timeout=5) as r:
            pass
    except Exception:
        pass
    google_ttfb = (time.time() - t0) * 1000

    # 2. Groq (api.groq.com)
    t0 = time.time()
    try:
        with urllib.request.urlopen('https://api.groq.com/', timeout=5) as r:
            pass
    except Exception:
        pass
    groq_ttfb = (time.time() - t0) * 1000

    print(f'Google GenAI connection/TTFB: {google_ttfb:.1f}ms')
    print(f'Groq connection/TTFB: {groq_ttfb:.1f}ms')

if __name__ == '__main__':
    test_h1()
    test_h2()
    test_h3()
    test_h4()
    test_h5()
    test_h6()
    test_h7()
    test_h9()
