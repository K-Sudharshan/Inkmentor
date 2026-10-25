#!/usr/bin/env python3
"""Baseline performance measurement script for InkMentor.
Runs 5 benchmark problems 3 times each against real backend and Gemini.
Measures:
- Request decode & validation
- LLM call duration and tokens
- SymPy verification (total, process startup/import, calculation)
- Retries count
- Total solve endpoint duration
- TTS synthesis duration
Outputs a markdown-ready table with stage, median, and worst time.
"""

import json
import statistics
import time
import urllib.request
from typing import Any, Dict, List

PROBLEMS = [
    "Differentiate y = sin(3x^2)",
    "Integrate x^2 dx",
    "Solve x^2 - 5x + 6 = 0",
    "x^2 + 6x + 6",
    "Differentiate y = x^3 + 4x",
]

BASE_URL = "http://127.0.0.1:8000"


def run_solve(question: str) -> Dict[str, Any]:
    payload = json.dumps({"question": question, "context": []}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/api/solve",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=90) as resp:
        wall_ms = (time.time() - t0) * 1000.0
        data = json.loads(resp.read().decode("utf-8"))
        server_timing = resp.headers.get("Server-Timing", "")
        return {
            "wall_ms": wall_ms,
            "verified": data.get("verified"),
            "attempts": data.get("attempts"),
            "timing": data.get("timing") or {},
            "server_timing": server_timing,
            "steps_count": len(data.get("steps") or []),
            "narration_step_0": data["steps"][0]["narration"] if data.get("steps") else "",
        }


def run_tts(text: str) -> float:
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/api/tts",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()
        return (time.time() - t0) * 1000.0


def main():
    print(f"=== INKMENTOR BASELINE LATENCY MEASUREMENT ===")
    print(f"Running 5 problems x 3 iterations = 15 runs on {BASE_URL}...\n")

    runs_data: List[Dict[str, Any]] = []

    for p_idx, question in enumerate(PROBLEMS, start=1):
        print(f"Problem {p_idx}/5: '{question}'")
        for it in range(1, 4):
            print(f"  Iteration {it}/3 ...", end="", flush=True)
            res = run_solve(question)
            t = res["timing"]
            # Also test TTS for first step narration if present
            tts_ms = 0.0
            if res["narration_step_0"]:
                tts_ms = run_tts(res["narration_step_0"])

            run_entry = {
                "problem": question,
                "iteration": it,
                "wall_ms": res["wall_ms"],
                "verified": res["verified"],
                "attempts": res["attempts"],
                "decode_ms": t.get("decode_ms", 0.0),
                "llm_ms": t.get("llm_ms", 0.0),
                "sympy_ms": t.get("sympy_ms", 0.0),
                "sympy_startup_ms": t.get("sympy_startup_ms", 0.0),
                "sympy_calc_ms": t.get("sympy_calc_ms", 0.0),
                "retries": t.get("retries", 0),
                "input_tokens": t.get("input_tokens", 0),
                "output_tokens": t.get("output_tokens", 0),
                "total_ms": t.get("total_ms", res["wall_ms"]),
                "tts_step0_ms": tts_ms,
            }
            runs_data.append(run_entry)
            print(
                f" OK: wall={res['wall_ms']:.0f}ms (llm={t.get('llm_ms', 0):.0f}ms, "
                f"sympy={t.get('sympy_ms', 0):.0f}ms [startup={t.get('sympy_startup_ms', 0):.0f}ms], "
                f"retries={t.get('retries', 0)}, ver={res['verified']}, att={res['attempts']})"
            )

    # Compute Summary Statistics
    def stats(key):
        vals = [r[key] for r in runs_data if r.get(key) is not None]
        return statistics.median(vals), max(vals)

    med_llm, worst_llm = stats("llm_ms")
    med_sympy, worst_sympy = stats("sympy_ms")
    med_sympy_start, worst_sympy_start = stats("sympy_startup_ms")
    med_sympy_calc, worst_sympy_calc = stats("sympy_calc_ms")
    med_decode, worst_decode = stats("decode_ms")
    med_total, worst_total = stats("total_ms")
    med_wall, worst_wall = stats("wall_ms")
    med_tts, worst_tts = stats("tts_step0_ms")

    # Output detailed table
    print("\n" + "=" * 80)
    print("BASELINE MEASUREMENT RESULTS (5 Problems x 3 Runs = 15 Samples)")
    print("=" * 80)
    print(f"{'Stage / Component':<36} | {'Median (ms)':<14} | {'Worst (ms)':<14}")
    print("-" * 72)
    print(f"{'Request Decode & Validation':<36} | {med_decode:<14.1f} | {worst_decode:<14.1f}")
    print(f"{'Gemini LLM Call(s)':<36} | {med_llm:<14.1f} | {worst_llm:<14.1f}")
    print(f"{'SymPy Verification (Total)':<36} | {med_sympy:<14.1f} | {worst_sympy:<14.1f}")
    print(f"{'  |-- Process Startup & SymPy Import':<36} | {med_sympy_start:<14.1f} | {worst_sympy_start:<14.1f}")
    print(f"{'  \\-- Pure Math Calculation':<36} | {med_sympy_calc:<14.1f} | {worst_sympy_calc:<14.1f}")
    print(f"{'Server /api/solve Total':<36} | {med_total:<14.1f} | {worst_total:<14.1f}")
    print(f"{'Client Wall Time (/api/solve)':<36} | {med_wall:<14.1f} | {worst_wall:<14.1f}")
    print(f"{'First-Step TTS Audio Latency':<36} | {med_tts:<14.1f} | {worst_tts:<14.1f}")
    print(f"{'Total Solve -> First Audio Path':<36} | {(med_wall + med_tts):<14.1f} | {(worst_wall + worst_tts):<14.1f}")
    print("=" * 80)

    # Save raw results as JSON for report reference
    with open("tools/baseline_measurements.json", "w", encoding="utf-8") as f:
        json.dump(runs_data, f, indent=2)
    print("Saved raw run records to tools/baseline_measurements.json")


if __name__ == "__main__":
    main()
