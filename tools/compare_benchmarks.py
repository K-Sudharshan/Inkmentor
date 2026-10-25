import json
import statistics

def load_data(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def summarize(entries):
    solve_to_stroke = [e["solve_to_stroke_ms"] for e in entries]
    circle_to_stroke = [e["circle_to_stroke_ms"] for e in entries]
    stage6_durations = []
    stage8_durations = []
    llm_durations = []

    for e in entries:
        m = e["marks"]
        table = {row["Stage"]: row["Duration (ms)"] for row in e.get("table", []) if "Stage" in row}
        # Stage 6
        if "6. Solve Clicked to Solve Sent" in table:
            stage6_durations.append(table["6. Solve Clicked to Solve Sent"])
        # Stage 8
        if "8. Solve Received to First Step Created" in table:
            stage8_durations.append(table["8. Solve Received to First Step Created"])
        # LLM from server
        srv = e.get("server", {})
        if "solve" in srv and "llm" in srv["solve"]:
            llm_durations.append(srv["solve"]["llm"])

    return {
        "count": len(entries),
        "solve_to_stroke_med": statistics.median(solve_to_stroke) if solve_to_stroke else 0,
        "solve_to_stroke_min": min(solve_to_stroke) if solve_to_stroke else 0,
        "solve_to_stroke_max": max(solve_to_stroke) if solve_to_stroke else 0,
        "circle_to_stroke_med": statistics.median(circle_to_stroke) if circle_to_stroke else 0,
        "stage6_med": statistics.median(stage6_durations) if stage6_durations else 0,
        "stage8_med": statistics.median(stage8_durations) if stage8_durations else 0,
        "llm_med": statistics.median(llm_durations) if llm_durations else 0,
    }

def main():
    base_file = "tools/out_baseline_measurements.json"
    post_file = "tools/out_post_measurements.json"

    base_entries = load_data(base_file)
    post_entries = load_data(post_file)

    b_sum = summarize(base_entries)
    p_sum = summarize(post_entries)

    print("\n" + "="*80)
    print("INKMENTOR PERFORMANCE BENCHMARK: BASELINE vs POST-OPTIMIZATION (15 RUNS)")
    print("="*80)
    print(f"{'Metric':<38} | {'Baseline':<12} | {'Post-Opt':<12} | {'Delta':<12}")
    print("-" * 80)

    diff_solve = p_sum['solve_to_stroke_med'] - b_sum['solve_to_stroke_med']
    pct_solve = (diff_solve / b_sum['solve_to_stroke_med']) * 100 if b_sum['solve_to_stroke_med'] else 0
    print(f"{'Solve-to-Stroke Median (ms)':<38} | {b_sum['solve_to_stroke_med']:>10.1f}ms | {p_sum['solve_to_stroke_med']:>10.1f}ms | {diff_solve:>+8.1f}ms ({pct_solve:+.1f}%)")

    diff_circle = p_sum['circle_to_stroke_med'] - b_sum['circle_to_stroke_med']
    pct_circle = (diff_circle / b_sum['circle_to_stroke_med']) * 100 if b_sum['circle_to_stroke_med'] else 0
    print(f"{'Circle-to-Stroke Median (ms)':<38} | {b_sum['circle_to_stroke_med']:>10.1f}ms | {p_sum['circle_to_stroke_med']:>10.1f}ms | {diff_circle:>+8.1f}ms ({pct_circle:+.1f}%)")

    diff_st6 = p_sum['stage6_med'] - b_sum['stage6_med']
    pct_st6 = (diff_st6 / b_sum['stage6_med']) * 100 if b_sum['stage6_med'] else 0
    print(f"{'Stage 6: Memory Retrieval (ms)':<38} | {b_sum['stage6_med']:>10.1f}ms | {p_sum['stage6_med']:>10.1f}ms | {diff_st6:>+8.1f}ms ({pct_st6:+.1f}%)")

    diff_st8 = p_sum['stage8_med'] - b_sum['stage8_med']
    pct_st8 = (diff_st8 / b_sum['stage8_med']) * 100 if b_sum['stage8_med'] else 0
    print(f"{'Stage 8: Step 0 Writing/TTS (ms)':<38} | {b_sum['stage8_med']:>10.1f}ms | {p_sum['stage8_med']:>10.1f}ms | {diff_st8:>+8.1f}ms ({pct_st8:+.1f}%)")

    diff_llm = p_sum['llm_med'] - b_sum['llm_med']
    print(f"{'Server LLM Solve Duration (ms)':<38} | {b_sum['llm_med']:>10.1f}ms | {p_sum['llm_med']:>10.1f}ms | {diff_llm:>+8.1f}ms")
    print("="*80)

    # Per-problem breakdown
    print("\nPER-PROBLEM MEDIAN COMPARISON (Solve-to-Stroke):")
    problems = list(dict.fromkeys([e["problem"] for e in base_entries]))
    for p in problems:
        b_p = statistics.median([e["solve_to_stroke_ms"] for e in base_entries if e["problem"] == p])
        p_p = statistics.median([e["solve_to_stroke_ms"] for e in post_entries if e["problem"] == p])
        d = p_p - b_p
        print(f"  • {p:<32}: {b_p:>7.1f}ms -> {p_p:>7.1f}ms ({d:>+7.1f}ms, {(d/b_p)*100:+.1f}%)")
    print("="*80)

if __name__ == "__main__":
    main()
