import json
import statistics
import time
import urllib.request

PROBLEMS = [
    "Differentiate y = sin(3x^2)",
    "Integrate x^2 dx",
    "Solve x^2 - 5x + 6 = 0",
    "x^2 + 6x + 6",
    "Differentiate y = x^3 + 4x",
]

results = []
print("=== MEASURING POST-OPTIMIZATION PERFORMANCE (5 Problems) ===", flush=True)
for idx, q in enumerate(PROBLEMS, 1):
    t0 = time.time()
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/solve",
        data=json.dumps({"question": q}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    wall_ms = round((time.time() - t0) * 1000.0, 1)
    timing = data.get("timing") or {}
    results.append({
        "question": q,
        "wall_ms": wall_ms,
        "timing": timing,
        "verified": data.get("verified"),
        "attempts": data.get("attempts"),
        "steps": len(data.get("steps", []))
    })
    print(f"[{idx}/5] '{q}': wall={wall_ms}ms, llm={timing.get('llm_ms')}ms, sympy={timing.get('sympy_ms')}ms, ver={data.get('verified')}, att={data.get('attempts')}", flush=True)

med_wall = statistics.median([r["wall_ms"] for r in results])
med_llm = statistics.median([r["timing"].get("llm_ms", 0) for r in results])
med_sympy = statistics.median([r["timing"].get("sympy_ms", 0) for r in results])
med_startup = statistics.median([r["timing"].get("sympy_startup_ms", 0) for r in results])
med_calc = statistics.median([r["timing"].get("sympy_calc_ms", 0) for r in results])

print("\n================ POST-OPTIMIZATION SUMMARY ================", flush=True)
print(f"Solve Wall Time Median: {med_wall:.1f}ms", flush=True)
print(f"LLM Latency Median:     {med_llm:.1f}ms", flush=True)
print(f"SymPy Total Median:     {med_sympy:.1f}ms", flush=True)
print(f"  |-- Startup Import:   {med_startup:.1f}ms", flush=True)
print(f"  \\-- Pure Math Calc:   {med_calc:.1f}ms", flush=True)
print("===========================================================", flush=True)

with open("tools/post_optimization_measurements.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)
