import os
import time
import wave
from pathlib import Path
from dotenv import load_dotenv

import sys
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
load_dotenv(project_root / "backend" / ".env")
from backend.tts import generate_tts_wav, get_wav_duration

out_dir = project_root / "tools" / "out"
out_dir.mkdir(parents=True, exist_ok=True)

samples = [
    ("differentiate_sin3x2.wav", "Let's use substitution with u equals 3x squared."),
    ("integrate_x2.wav", "Apply the power rule by adding one to the exponent and dividing by the new power."),
    ("solve_quadratic.wav", "Factor the quadratic into x minus two times x minus three equals zero.")
]

print("Starting generation of 3 sample audio files...")
for i, (fname, text) in enumerate(samples):
    if i > 0:
        print(f"Waiting 22s before sample {i+1} to respect rate limit...")
        time.sleep(22)
    print(f"Generating {fname} for: '{text}'")
    audio_bytes = generate_tts_wav(text)
    dest = out_dir / fname
    dest.write_bytes(audio_bytes)
    dur = get_wav_duration(audio_bytes)
    print(f"Saved {dest.name} ({len(audio_bytes)} bytes, {dur:.2f}s)")

print("All 3 sample audio files generated successfully.")
