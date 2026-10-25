import os
import shutil
from backend.tts import get_cache_key

phrases = [
    ("gemini-3.8-flash-lite-tts", "Puck", "Let's use substitution for the inside expression.", "tools/out/differentiate_sin3x2.wav"),
    ("gemini-3.8-flash-tts", "Puck", "Let's use substitution for the inside expression.", "tools/out/differentiate_sin3x2.wav"),
    ("gemini-3.8-flash-lite-tts", "Puck", "Let's use substitution with u equals 3x squared, so du dx is 6x.", "tools/out/sample_sin_3x2.wav"),
    ("gemini-3.8-flash-tts", "Puck", "Let's use substitution with u equals 3x squared, so du dx is 6x.", "tools/out/sample_sin_3x2.wav"),
    ("gemini-3.8-flash-lite-tts", "Puck", "Applying the power rule, we increase the exponent by one and divide by three.", "tools/out/sample_integrate_x2.wav"),
    ("gemini-3.8-flash-lite-tts", "Puck", "Factoring gives x minus 2 times x minus 3 equals zero, so x equals 2 or 3.", "tools/out/sample_solve_quadratic.wav")
]

os.makedirs("backend/.cache/audio", exist_ok=True)
for model, voice, text, src in phrases:
    if os.path.exists(src):
        k = get_cache_key(model, voice, text)
        dst = os.path.join("backend/.cache/audio", f"{k}.wav")
        shutil.copyfile(src, dst)
        print(f"Cached: {src} -> {dst}")
