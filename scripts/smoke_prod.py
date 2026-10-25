#!/usr/bin/env python3
"""
InkMentor Production Smoke Test Suite
Usage:
    python scripts/smoke_prod.py <BASE_URL> [--tts]

Example:
    python scripts/smoke_prod.py https://inkmentor.vercel.app
    python scripts/smoke_prod.py http://127.0.0.1:8000 --tts
"""

import argparse
import base64
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def make_request(
    url: str,
    method: str = "GET",
    data: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 30.0,
) -> Tuple[int, bytes, Dict[str, str], float]:
    """Sends HTTP request and returns (status_code, body_bytes, headers_dict, duration_ms)."""
    req_headers = {"User-Agent": "InkMentor-SmokeTest/1.0"}
    if headers:
        req_headers.update(headers)

    body_bytes = None
    if data is not None:
        body_bytes = json.dumps(data).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body_bytes, headers=req_headers, method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            dur_ms = (time.time() - t0) * 1000.0
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            return resp.status, resp.read(), resp_headers, dur_ms
    except urllib.error.HTTPError as he:
        dur_ms = (time.time() - t0) * 1000.0
        resp_headers = {k.lower(): v for k, v in he.headers.items()}
        return he.code, he.read(), resp_headers, dur_ms
    except Exception as exc:
        dur_ms = (time.time() - t0) * 1000.0
        raise RuntimeError(f"Connection failed: {exc}") from exc


def main():
    parser = argparse.ArgumentParser(description="InkMentor Production Smoke Tests")
    parser.add_argument("base_url", help="Base URL of deployment (e.g. https://inkmentor.vercel.app)")
    parser.add_argument("--tts", action="store_true", help="Include real TTS audio synthesis check (spares quota)")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    print(f"\n=======================================================")
    print(f"  InkMentor Production Smoke Test: {base_url}")
    print(f"  Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print(f"=======================================================\n")

    results = []
    overall_passed = True

    def record(name: str, passed: bool, dur_ms: float, detail: str = ""):
        nonlocal overall_passed
        status_str = "PASS" if passed else "FAIL"
        if not passed:
            overall_passed = False
        results.append((name, status_str, dur_ms, detail))
        print(f"[{status_str}] {name} ({dur_ms:.1f}ms) - {detail}")

    # 1. Frontend HTML "/"
    try:
        code, body, hdrs, dur = make_request(f"{base_url}/")
        passed = code == 200 and b"InkMentor" in body
        record("Static Root HTML (/)", passed, dur, f"HTTP {code}, {len(body)} bytes")
    except Exception as e:
        record("Static Root HTML (/)", False, 0.0, str(e))

    # 2. Font Asset "/fonts/Caveat-Regular.ttf"
    try:
        code, body, hdrs, dur = make_request(f"{base_url}/fonts/Caveat-Regular.ttf")
        passed = code == 200 and len(body) > 100000
        record("Font Asset (/fonts/Caveat-Regular.ttf)", passed, dur, f"HTTP {code}, {len(body)} bytes")
    except Exception as e:
        record("Font Asset (/fonts/Caveat-Regular.ttf)", False, 0.0, str(e))

    # 3. Static Centerlines JSON
    try:
        code, body, hdrs, dur = make_request(f"{base_url}/reenie_centerlines.json")
        passed = code == 200 and len(body) > 1000
        record("Static Asset (/reenie_centerlines.json)", passed, dur, f"HTTP {code}, {len(body)} bytes")
    except Exception as e:
        record("Static Asset (/reenie_centerlines.json)", False, 0.0, str(e))

    # 4. Static Hershey Glyphs JSON
    try:
        code, body, hdrs, dur = make_request(f"{base_url}/hershey_glyphs.json")
        passed = code == 200 and len(body) > 1000
        record("Static Asset (/hershey_glyphs.json)", passed, dur, f"HTTP {code}, {len(body)} bytes")
    except Exception as e:
        record("Static Asset (/hershey_glyphs.json)", False, 0.0, str(e))

    # 5. Fast Health Endpoint "/api/health"
    try:
        code, body, hdrs, dur = make_request(f"{base_url}/api/health?verbose=true")
        data = json.loads(body.decode("utf-8")) if code == 200 else {}
        passed = code == 200 and data.get("status") == "ok"
        detail = f"HTTP {code}, status={data.get('status')}, keys={data.get('keys')}, mem={data.get('memory_index_loaded')}"
        record("Fast Health Check (/api/health)", passed, dur, detail)
    except Exception as e:
        record("Fast Health Check (/api/health)", False, 0.0, str(e))

    # 6. Real Math Solver "/api/solve" ("Differentiate y = sin(3x^2)")
    try:
        solve_payload = {
            "question": "Differentiate y = sin(3x^2)",
            "context": []
        }
        code, body, hdrs, dur = make_request(f"{base_url}/api/solve", method="POST", data=solve_payload, timeout=50.0)
        data = json.loads(body.decode("utf-8")) if code == 200 else {}
        verified = data.get("verified", False)
        attempts = data.get("attempts", 0)
        timing = data.get("timing", {})
        server_timing = hdrs.get("server-timing", "n/a")
        passed = code == 200 and verified is True
        detail = f"verified={verified}, attempts={attempts}, steps={len(data.get('steps', []))}, Server-Timing='{server_timing}'"
        record("Math Solver Verification (/api/solve)", passed, dur, detail)
    except Exception as e:
        record("Math Solver Verification (/api/solve)", False, 0.0, str(e))

    # 7. Real Vision Recognize Endpoint "/api/recognize"
    try:
        rec_payload = {
            "image_base64": TINY_PNG_B64,
            "media_type": "image/png"
        }
        code, body, hdrs, dur = make_request(f"{base_url}/api/recognize", method="POST", data=rec_payload, timeout=30.0)
        data = json.loads(body.decode("utf-8")) if code == 200 else {}
        passed = code == 200 and "readable" in data
        record("Vision Recognition (/api/recognize)", passed, dur, f"HTTP {code}, readable={data.get('readable')}")
    except Exception as e:
        record("Vision Recognition (/api/recognize)", False, 0.0, str(e))

    # 8. Unprocessable Entity 422 Case "/api/recognize"
    try:
        bad_payload = {"image_base64": "not_a_valid_base64!!!", "media_type": "image/png"}
        code, body, hdrs, dur = make_request(f"{base_url}/api/recognize", method="POST", data=bad_payload)
        passed = code == 422
        record("422 Validation Error Handling (/api/recognize)", passed, dur, f"HTTP {code} (expected 422)")
    except Exception as e:
        record("422 Validation Error Handling (/api/recognize)", False, 0.0, str(e))

    # 9. TTS Status Endpoint "/api/tts/status"
    try:
        code, body, hdrs, dur = make_request(f"{base_url}/api/tts/status")
        data = json.loads(body.decode("utf-8")) if code == 200 else {}
        passed = code == 200 and "configured" in data
        record("TTS Status (/api/tts/status)", passed, dur, f"configured={data.get('configured')}, voice={data.get('voice')}")
    except Exception as e:
        record("TTS Status (/api/tts/status)", False, 0.0, str(e))

    # 10. Optional Real TTS Audio Call "--tts"
    if args.tts:
        try:
            tts_payload = {"text": "Verified with SymPy.", "position": "middle"}
            code, body, hdrs, dur = make_request(f"{base_url}/api/tts", method="POST", data=tts_payload, timeout=20.0)
            passed = code in (200, 503)
            prov = hdrs.get("x-tts-provider", "unknown")
            detail = f"HTTP {code}, provider={prov}, size={len(body)} bytes"
            record("Real TTS Audio Synthesis (/api/tts)", passed, dur, detail)
        except Exception as e:
            record("Real TTS Audio Synthesis (/api/tts)", False, 0.0, str(e))
    else:
        print("[SKIP] Real TTS Audio Synthesis (/api/tts) skipped to protect quota (pass --tts to run)")

    print(f"\n=======================================================")
    print(f"  Summary: {'ALL TESTS PASSED' if overall_passed else 'SOME TESTS FAILED'}")
    print(f"=======================================================\n")

    sys.exit(0 if overall_passed else 1)


if __name__ == "__main__":
    main()
