#!/usr/bin/env python3
"""Smoke test script for Gemini Text-To-Speech.
Makes one real call, saves the audio to a temporary file,
and prints size, format, and duration.
Skips cleanly if no API key is present.
"""

import os
import sys
import tempfile
import wave
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

# Load environment
env_path = project_root / "backend" / ".env"
load_dotenv(dotenv_path=env_path)

api_key = os.environ.get("LLM_API_KEY", "").strip()
if not api_key:
    print("SKIPPED: LLM_API_KEY not found in environment. Skipping real TTS smoke call.")
    sys.exit(0)

from backend.tts import generate_tts_wav, get_tts_config

def main():
    model, voice, rate_limit, timeout = get_tts_config()
    test_text = "Let's differentiate the expression using the chain rule."
    print(f"Running TTS Smoke Test...")
    print(f"Model: {model}")
    print(f"Voice: {voice}")
    print(f"Input text: '{test_text}' ({len(test_text)} chars)")

    try:
        wav_bytes = generate_tts_wav(test_text)
    except Exception as exc:
        print(f"ERROR: TTS generation failed: {exc}")
        sys.exit(1)

    # Save to temp file
    temp_dir = tempfile.gettempdir()
    out_path = os.path.join(temp_dir, "inkmentor_tts_smoke.wav")
    with open(out_path, "wb") as f:
        f.write(wav_bytes)

    # Verify WAV header
    with wave.open(out_path, "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        n_frames = wf.getnframes()
        duration = n_frames / float(framerate)

    print("\n--- Smoke Test Succeeded ---")
    print(f"Audio file: {out_path}")
    print(f"File size: {len(wav_bytes)} bytes")
    print(f"Audio format: WAV (PCM 16-bit)")
    print(f"Channels: {n_channels} (Mono)")
    print(f"Bit depth: {sampwidth * 8}-bit")
    print(f"Sample rate: {framerate} Hz")
    print(f"Duration: {duration:.2f} seconds")
    print("----------------------------\n")
    sys.exit(0)

if __name__ == "__main__":
    main()
