import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath("."))

from google import genai
from google.genai import types

from backend.prompts import SYSTEM_PROMPT, build_user_prompt
from backend.solver import parse_llm_output
from backend.verify import verify

PROBLEMS = [
    "Differentiate y = sin(3x^2)",
    "Integrate x^2 dx",
    "Solve x^2 - 5x + 6 = 0",
    "x^2 + 6x + 6",
    "Differentiate y = x^3 + 4x",
]

CANDIDATES = [
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-flash-latest",
]


def get_api_key() -> str:
    key = os.environ.get("LLM_API_KEY")
    if not key:
        with open("backend/.env", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("LLM_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    break
    if not key:
        raise RuntimeError("LLM_API_KEY not found")
    return key


def main():
    api_key = get_api_key()
    client = genai.Client(api_key=api_key)

    print("=== GEMINI CANDIDATE MODEL BENCHMARK (5 Problems) ===", flush=True)
    summary_results = {}

    for model in CANDIDATES:
        print(f"\nEvaluating Model: {model} ...", flush=True)
        durations = []
        in_tokens = []
        out_tokens = []
        passes = 0
        total_eval = 0

        for idx, prob in enumerate(PROBLEMS, 1):
            prompt = build_user_prompt(prob, [])
            t0 = time.time()
            try:
                try:
                    conf = types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.0,
                        max_output_tokens=1024,
                        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL),
                    )
                    resp = client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=conf,
                    )
                except Exception:
                    conf = types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.0,
                        max_output_tokens=1024,
                    )
                    resp = client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=conf,
                    )

                dur_ms = round((time.time() - t0) * 1000.0, 1)
                durations.append(dur_ms)
                if resp.usage_metadata:
                    in_tokens.append(getattr(resp.usage_metadata, "prompt_token_count", 0) or 0)
                    out_tokens.append(getattr(resp.usage_metadata, "candidates_token_count", 0) or 0)

                output, parse_err = parse_llm_output(resp.text)
                is_valid = False
                if output:
                    ver, _, _ = verify(
                        output.task_type,
                        output.variable,
                        output.expression_sympy,
                        output.final_answer_sympy,
                        timeout_seconds=5.0,
                    )
                    if ver:
                        is_valid = True
                        passes += 1

                total_eval += 1
                status = "PASS" if is_valid else "FAIL"
                print(f"  [{idx}/5] '{prob}': {dur_ms}ms ({status})", flush=True)

            except Exception as e:
                dur_ms = round((time.time() - t0) * 1000.0, 1)
                total_eval += 1
                print(f"  [{idx}/5] '{prob}': ERROR ({e}) in {dur_ms}ms", flush=True)

        avg_dur = round(sum(durations) / len(durations), 1) if durations else 0.0
        avg_in = round(sum(in_tokens) / len(in_tokens), 1) if in_tokens else 0.0
        avg_out = round(sum(out_tokens) / len(out_tokens), 1) if out_tokens else 0.0
        pass_rate = f"{(passes / total_eval * 100):.0f}%" if total_eval > 0 else "0%"

        summary_results[model] = {
            "avg_latency_ms": avg_dur,
            "avg_in_tokens": avg_in,
            "avg_out_tokens": avg_out,
            "pass_rate": pass_rate,
            "samples": len(durations),
        }

    print("\n" + "=" * 80, flush=True)
    print("CANDIDATE MODEL BENCHMARK SUMMARY TABLE", flush=True)
    print("=" * 80, flush=True)
    print(f"{'Model Name':<28} | {'Avg Latency (ms)':<16} | {'Avg Out Tokens':<14} | {'SymPy Pass Rate'}", flush=True)
    print("-" * 80, flush=True)
    for m, d in summary_results.items():
        print(f"{m:<28} | {d['avg_latency_ms']:<16.1f} | {d['avg_out_tokens']:<14.1f} | {d['pass_rate']}", flush=True)
    print("=" * 80, flush=True)

    with open("tools/candidate_benchmark.json", "w", encoding="utf-8") as f:
        json.dump(summary_results, f, indent=2)


if __name__ == "__main__":
    main()
