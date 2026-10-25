import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
import wave
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv

# Load backend environment variables
backend_env = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))
if os.path.exists(backend_env):
    load_dotenv(backend_env)

API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
MODEL = os.environ.get("GROQ_TTS_MODEL", "canopylabs/orpheus-v1-english").strip()
OUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools", "out", "tts"))
os.makedirs(OUT_DIR, exist_ok=True)

SAMPLE_A = "Alright, let's break this one down together. We've got a function inside a function, so the chain rule is our friend."
SAMPLE_B = "And that's our answer, six x cosine of three x squared. You can be proud of that one!"

VERIFIED_VOICES = ["autumn", "diana", "hannah", "austin", "daniel", "troy"]

ROUND2_DIRECTIONS = [
    "cheerful",
    "dramatically",
    "professionally",
    # Experiments (unconfirmed):
    "excited",
    "playfully",
    "enthusiastic",
    "upbeat",
    "warmly",
]


def call_groq_tts(text: str, voice: str, direction: Optional[str] = None) -> bytes:
    if not API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured in backend/.env")

    dir_clean = direction.strip() if direction else ""
    input_text = f"[{dir_clean}] {text}" if dir_clean else text

    payload = json.dumps({
        "model": MODEL,
        "voice": voice,
        "input": input_text,
        "response_format": "wav"
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/audio/speech",
        data=payload,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "InkMentor-TTS/1.0"
        }
    )

    with urllib.request.urlopen(req, timeout=15.0) as resp:
        return resp.read()


def get_wav_duration_and_size(wav_bytes: bytes) -> Tuple[float, int]:
    size = len(wav_bytes)
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        dur = wf.getnframes() / float(wf.getframerate()) if wf.getframerate() > 0 else 0.0
    return dur, size


def run_grid():
    print(f"=== Groq Orpheus TTS Sample Grid Generation ===")
    print(f"Model: {MODEL}")
    print(f"Output directory: {OUT_DIR}")
    print(f"Voices: {VERIFIED_VOICES}")
    print()

    results: List[Dict] = []
    round1_map: Dict[str, Dict[str, float]] = {v: {} for v in VERIFIED_VOICES}

    # ROUND 1: All verified voices, no direction vs cheerful on Sample A
    print("--- ROUND 1: Verified Voices (no direction vs [cheerful] on Sample A) ---")
    for voice in VERIFIED_VOICES:
        for d in [None, "cheerful"]:
            dir_label = d if d else "none"
            filename = f"{voice}_{dir_label}_sampleA.wav"
            filepath = os.path.join(OUT_DIR, filename)

            print(f"Generating {voice} ({dir_label})... ", end="", flush=True)
            try:
                wav_bytes = call_groq_tts(SAMPLE_A, voice, d)
                dur, size = get_wav_duration_and_size(wav_bytes)
                with open(filepath, "wb") as f:
                    f.write(wav_bytes)
                round1_map[voice][dir_label] = dur
                results.append({
                    "round": 1,
                    "sample": "A",
                    "voice": voice,
                    "direction": dir_label,
                    "duration": dur,
                    "size": size,
                    "file": filename,
                    "path": filepath,
                    "flagged": False,
                    "flag_reason": ""
                })
                print(f"OK ({dur:.2f}s, {size} bytes)")
            except urllib.error.HTTPError as he:
                print(f"HTTP Error {he.code}: {he.read().decode()}")
                if he.code == 429:
                    print("RATE LIMIT 429 HIT. Stopping execution as per hard rules.")
                    return results
            except Exception as e:
                print(f"Error: {e}")
            time.sleep(2.5)

    # Pick top 2 voices from Round 1
    # Proxy: voice whose [cheerful] duration differs most from [none]
    voice_diffs = []
    for v in VERIFIED_VOICES:
        d_none = round1_map[v].get("none")
        d_cheer = round1_map[v].get("cheerful")
        if d_none and d_cheer:
            diff = abs(d_cheer - d_none)
            ratio = d_cheer / d_none
            voice_diffs.append((v, diff, ratio, d_none, d_cheer))

    voice_diffs.sort(key=lambda x: x[1], reverse=True)
    print("\nRound 1 Responsiveness Metric (duration delta cheerful vs none; note: this duration delta is a weak proxy):")
    for v, diff, ratio, d0, d1 in voice_diffs:
        print(f"  {v:8s}: |cheerful - none| = {diff:.2f}s (ratio: {ratio:.2f}x; none={d0:.2f}s, cheerful={d1:.2f}s)")

    if len(voice_diffs) < 2:
        print("Not enough voices completed Round 1.")
        top_2_voices = [v for v, _, _, _, _ in voice_diffs]
    else:
        top_2_voices = [voice_diffs[0][0], voice_diffs[1][0]]

    print(f"\nTop 2 Selected Voices for Round 2: {top_2_voices}")

    # ROUND 2: Directions on Sample A & Sample B for the 2 selected voices
    print("\n--- ROUND 2: Expressive Directions on Sample A and Sample B ---")
    for voice in top_2_voices:
        base_dur_A = round1_map[voice].get("none", 4.0)
        # First get none baseline for Sample B
        print(f"Generating {voice} (none) for Sample B... ", end="", flush=True)
        try:
            wav_B_none = call_groq_tts(SAMPLE_B, voice, None)
            dur_B_none, size_B_none = get_wav_duration_and_size(wav_B_none)
            fname_B_none = f"{voice}_none_sampleB.wav"
            with open(os.path.join(OUT_DIR, fname_B_none), "wb") as f:
                f.write(wav_B_none)
            results.append({
                "round": 2,
                "sample": "B",
                "voice": voice,
                "direction": "none",
                "duration": dur_B_none,
                "size": size_B_none,
                "file": fname_B_none,
                "path": os.path.join(OUT_DIR, fname_B_none),
                "flagged": False,
                "flag_reason": ""
            })
            print(f"OK ({dur_B_none:.2f}s, {size_B_none} bytes)")
        except Exception as e:
            print(f"Error: {e}")
            dur_B_none = 3.5
        time.sleep(2.5)

        for direction in ROUND2_DIRECTIONS:
            for s_name, s_text, base_dur in [("A", SAMPLE_A, base_dur_A), ("B", SAMPLE_B, dur_B_none)]:
                # If Sample A cheerful was already recorded, reuse
                if s_name == "A" and direction == "cheerful" and "cheerful" in round1_map[voice]:
                    continue

                filename = f"{voice}_{direction}_sample{s_name}.wav"
                filepath = os.path.join(OUT_DIR, filename)
                print(f"Generating {voice} [{direction}] Sample {s_name}... ", end="", flush=True)
                try:
                    wav_bytes = call_groq_tts(s_text, voice, direction)
                    dur, size = get_wav_duration_and_size(wav_bytes)
                    with open(filepath, "wb") as f:
                        f.write(wav_bytes)

                    ratio = dur / base_dur if base_dur > 0 else 1.0
                    flagged = ratio > 1.35
                    flag_reason = f"Duration {dur:.2f}s is {ratio:.2f}x baseline ({base_dur:.2f}s) - suspect spoken direction" if flagged else ""

                    results.append({
                        "round": 2,
                        "sample": s_name,
                        "voice": voice,
                        "direction": direction,
                        "duration": dur,
                        "size": size,
                        "file": filename,
                        "path": filepath,
                        "flagged": flagged,
                        "flag_reason": flag_reason
                    })
                    flag_str = " [FLAGGED - spoken direction?]" if flagged else ""
                    print(f"OK ({dur:.2f}s, {size} bytes){flag_str}")
                except urllib.error.HTTPError as he:
                    print(f"HTTP Error {he.code}: {he.read().decode()}")
                    if he.code == 429:
                        print("RATE LIMIT 429 HIT. Stopping execution as per hard rules.")
                        return results
                except Exception as e:
                    print(f"Error: {e}")
                time.sleep(2.5)

    return results


if __name__ == "__main__":
    res = run_grid()
    print("\n=== SUMMARY TABLE ===")
    print("| Voice | Direction | Sample | Duration (s) | Size (B) | Flagged | Filename |")
    print("|---|---|---|---|---|---|---|")
    for r in res:
        flag_status = "YES (spoken?)" if r["flagged"] else "No"
        print(f"| `{r['voice']}` | `{r['direction']}` | {r['sample']} | {r['duration']:.2f} | {r['size']} | {flag_status} | `{r['file']}` |")
