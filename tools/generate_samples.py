import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv("backend/.env")

from backend.tts import generate_tts_wav

os.makedirs("tools/out", exist_ok=True)

samples = [
    ("tools/out/sample_sin_3x2.wav", "Let's use u-substitution with u equals 3x squared, so du dx is 6x."),
    ("tools/out/sample_integrate_x2.wav", "Applying the power rule, we increase the exponent by one and divide by three."),
    ("tools/out/sample_solve_quadratic.wav", "Factoring gives x minus 2 times x minus 3 equals zero, so x equals 2 or 3.")
]

for idx, (path, text) in enumerate(samples):
    print(f"[{idx+1}/3] Generating: {path} for text: '{text}'")
    wav = generate_tts_wav(text)
    with open(path, "wb") as f:
        f.write(wav)
    duration = (len(wav) - 44) / 48000.0
    print(f"Saved {path} ({len(wav)} bytes, {duration:.2f}s)")
    if idx < len(samples) - 1:
        print("Waiting 25s between sample generations for rate limit...")
        time.sleep(25)

print("All 3 sample audio files generated successfully!")
