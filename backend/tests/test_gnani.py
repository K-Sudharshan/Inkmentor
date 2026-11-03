import base64
import io
import os
import wave
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.tts import (
    clear_cache,
    format_gnani_timbre_text,
    pcm_to_wav,
    synthesize_speech_gnani,
    transcribe_speech_gnani,
)

client = TestClient(app)


def make_dummy_pcm(duration_sec: float = 0.5, sample_rate: int = 24000) -> bytes:
    num_samples = int(duration_sec * sample_rate)
    return b"\x00\x00" * num_samples


@pytest.fixture(autouse=True)
def reset_cache():
    clear_cache()
    yield
    clear_cache()


def test_gnani_timbre_text_pacing_formatting():
    """format_gnani_timbre_text adds <pauses> between sentences for timbre-v3.0."""
    raw = "Let us substitute u = x squared. Then du = 2x dx."
    formatted = format_gnani_timbre_text(raw, "timbre-v3.0")
    assert "<pauses>" in formatted
    assert formatted == "Let us substitute u = x squared. <pauses> Then du = 2x dx."

    # Older model or existing tags should not duplicate
    assert format_gnani_timbre_text(raw, "timbre-v2.5") == raw
    assert format_gnani_timbre_text("Wait <pauses> here.", "timbre-v3.0") == "Wait <pauses> here."


def test_gnani_tts_synthesis_returns_valid_wav():
    """synthesize_speech_gnani calls Vachana API and returns canonical WAV."""
    fake_wav = pcm_to_wav(make_dummy_pcm(0.5), sample_rate=24000)
    fake_b64 = base64.b64encode(fake_wav).decode("utf-8")

    mock_resp = MagicMock()
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.headers = {"Content-Type": "application/json"}
    mock_resp.read.return_value = f'{{"audio_content": "{fake_b64}"}}'.encode("utf-8")

    with patch.dict(os.environ, {"GNANI_API_KEY": "test_gnani_key_123"}):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            wav_out = synthesize_speech_gnani(
                text="Integrate 2x dx.",
                model_name="timbre-v3.0",
                voice_name="Nalini",
                language="en-IN",
            )
            assert isinstance(wav_out, bytes)
            with wave.open(io.BytesIO(wav_out), "rb") as wf:
                assert wf.getframerate() == 24000
                assert wf.getnchannels() == 1


def test_gnani_tts_endpoint_uses_gnani_provider():
    """POST /api/tts returns Gnani provider headers when GNANI_API_KEY is configured."""
    fake_wav = pcm_to_wav(make_dummy_pcm(0.4), sample_rate=24000)
    with patch.dict(os.environ, {"GNANI_API_KEY": "test_gnani_key_xyz", "TTS_PROVIDER": "gnani"}):
        with patch("backend.tts.synthesize_speech_gnani", return_value=fake_wav) as mock_gnani:
            resp = client.post("/api/tts", json={"text": "Step 1: Simplify expression."})
            assert resp.status_code == 200
            assert resp.headers["x-tts-provider"] == "gnani"
            mock_gnani.assert_called_once()


def test_gnani_fallback_to_groq_when_gnani_fails():
    """When Gnani fails, the chain falls back to subsequent providers."""
    fake_wav = pcm_to_wav(make_dummy_pcm(0.3), sample_rate=24000)
    env_vars = {
        "GNANI_API_KEY": "test_gnani_key",
        "TTS_PROVIDER": "gnani",
        "TTS_DISABLE_GEMINI": "true",  # skip gemini to test groq fallback directly
    }
    with patch.dict(os.environ, env_vars):
        with patch("backend.tts.synthesize_speech_gnani", side_effect=RuntimeError("GNANI_QUOTA_EXCEEDED 429")):
            with patch("backend.tts.synthesize_speech_groq", return_value=fake_wav) as mock_groq:
                resp = client.post("/api/tts", json={"text": "Step 2: Differentiate."})
                assert resp.status_code == 200
                assert resp.headers["x-tts-provider"] == "groq"
                assert int(resp.headers["x-tts-attempts"]) >= 2
                mock_groq.assert_called_once()


def test_gnani_key_redacted_on_error():
    """Gnani API key is never leaked in HTTP 502 responses."""
    secret = "gnani_super_secret_key_999"
    with patch.dict(os.environ, {"GNANI_API_KEY": secret, "TTS_PROVIDER": "gnani"}):
        with patch("backend.tts.synthesize_speech_provider", side_effect=RuntimeError(f"Vachana failure for {secret}")):
            resp = client.post("/api/tts", json={"text": "Step 2: Take derivatives."})
            assert resp.status_code == 502
            assert secret not in resp.text
            assert "[REDACTED]" in resp.json()["detail"]


def test_gnani_stt_json_and_raw_payload():
    """POST /api/stt handles both JSON base64 and raw audio bytes with Gnani Prisma."""
    fake_audio = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"

    with patch("backend.main.transcribe_speech_gnani", return_value="integrate x squared dx") as mock_stt:
        # JSON format
        b64_audio = base64.b64encode(fake_audio).decode("utf-8")
        resp_json = client.post(
            "/api/stt",
            json={"audio_base64": b64_audio, "language": "indic-auto"},
        )
        assert resp_json.status_code == 200
        data = resp_json.json()
        assert data["transcript"] == "integrate x squared dx"
        assert data["provider"] == "gnani"
        assert data["model"] == "prisma-v3.0"

        # Raw audio format
        resp_raw = client.post(
            "/api/stt?language=hi-IN",
            content=fake_audio,
            headers={"Content-Type": "audio/wav"},
        )
        assert resp_raw.status_code == 200
        assert resp_raw.json()["transcript"] == "integrate x squared dx"
