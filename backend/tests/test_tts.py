import io
import os
import time
import wave
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.tts import clear_cache, pcm_to_wav

client = TestClient(app)


def make_dummy_pcm(duration_sec: float = 1.0, sample_rate: int = 24000) -> bytes:
    """Generates synthetic 24kHz 16-bit mono PCM bytes."""
    num_samples = int(duration_sec * sample_rate)
    return b"\x00\x00" * num_samples


@pytest.fixture(autouse=True)
def reset_tts_state():
    clear_cache()
    yield
    clear_cache()


def test_1_tts_status_endpoint():
    """GET /api/tts/status returns configured model, voice, and rate without making paid calls."""
    resp = client.get("/api/tts/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "configured" in data
    assert "model" in data
    assert "voice" in data
    assert "rate_per_min" in data
    assert data["voice"] in ("Puck", "autumn")


def test_2_valid_text_returns_playable_wav_with_correct_header():
    """POST /api/tts with valid text returns playable 24kHz WAV with valid header."""
    fake_pcm = make_dummy_pcm(1.2)
    fake_wav = pcm_to_wav(fake_pcm, sample_rate=24000)

    with patch("backend.tts.synthesize_speech_provider", return_value=fake_wav) as mock_provider:
        resp = client.post("/api/tts", json={"text": "Let us differentiate this step."})
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "audio/wav"
        audio_bytes = resp.content
        assert len(audio_bytes) > 44

        # Prove it plays by decoding it back using python wave module
        with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 24000
            frames = wf.readframes(wf.getnframes())
            assert len(frames) == len(fake_pcm)

        mock_provider.assert_called_once()


def test_3_cache_hit_does_not_call_provider_twice():
    """Identical narration text hits in-memory LRU cache and avoids duplicate provider calls."""
    fake_wav = pcm_to_wav(make_dummy_pcm(0.8), sample_rate=24000)

    with patch("backend.tts.synthesize_speech_provider", return_value=fake_wav) as mock_provider:
        resp1 = client.post("/api/tts", json={"text": "Solve for x in the quadratic equation."})
        assert resp1.status_code == 200
        assert mock_provider.call_count == 1

        resp2 = client.post("/api/tts", json={"text": "Solve for x in the quadratic equation."})
        assert resp2.status_code == 200
        assert resp1.content == resp2.content
        # Provider must still have been called only once
        assert mock_provider.call_count == 1


def test_4_empty_or_whitespace_text_is_422():
    """Empty or all-whitespace text must be rejected with 422."""
    resp1 = client.post("/api/tts", json={"text": ""})
    assert resp1.status_code == 422

    resp2 = client.post("/api/tts", json={"text": "   \n\t  "})
    assert resp2.status_code == 422


def test_5_over_long_text_is_422():
    """Text exceeding 300 characters must be rejected with 422."""
    long_text = "a" * 301
    resp = client.post("/api/tts", json={"text": long_text})
    assert resp.status_code == 422
    assert "300" in resp.json()["detail"]


def test_6_control_characters_rejected_is_422():
    """Control characters (e.g. \x00, \x07, \x1b) must be rejected with 422."""
    resp1 = client.post("/api/tts", json={"text": "Hello\x00World"})
    assert resp1.status_code == 422

    resp2 = client.post("/api/tts", json={"text": "Bell\x07ring"})
    assert resp2.status_code == 422


def test_7_provider_error_is_502_with_no_key_in_body():
    """Upstream provider errors return 502 and never expose the secret API key."""
    fake_secret_key = "AIzaSySecretFakeApiKey12345"
    with patch.dict(os.environ, {"LLM_API_KEY": fake_secret_key}):
        with patch("backend.tts.synthesize_speech_provider", side_effect=RuntimeError(f"Google error with {fake_secret_key}")):
            resp = client.post("/api/tts", json={"text": "Valid question text"})
            assert resp.status_code == 502
            assert fake_secret_key not in resp.text
            assert "[REDACTED]" in resp.json()["detail"] or "TTS provider error" in resp.json()["detail"]


def test_8_timeout_is_502():
    """TTS provider timeout returns 502 without traceback leaks."""
    with patch("backend.tts.synthesize_speech_provider", side_effect=TimeoutError("TTS provider call timed out after 8.0s")):
        resp = client.post("/api/tts", json={"text": "Compute derivative of sin(x)"})
        assert resp.status_code == 502
        assert "timed out" in resp.json()["detail"].lower() or "timeout" in resp.json()["detail"].lower()



def test_9_instruction_string_not_returned_to_client():
    """The client receives audio bytes (Content-Type audio/wav), never prompt instructions."""
    fake_wav = pcm_to_wav(make_dummy_pcm(0.5), sample_rate=24000)
    with patch("backend.tts.synthesize_speech_provider", return_value=fake_wav):
        resp = client.post("/api/tts", json={"text": "Step 1: factor the numerator"})
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "audio/wav"
        # Body is binary audio, not JSON containing prompt instruction
        assert not resp.text.startswith("{")
        assert "Say this warmly" not in resp.text


def test_10_rate_limit_exceeded_is_429():
    """Exceeding TTS_RATE_PER_MIN returns 429 Too Many Requests."""
    fake_wav = pcm_to_wav(make_dummy_pcm(0.1), sample_rate=24000)
    with patch.dict(os.environ, {"TTS_RATE_PER_MIN": "3"}):
        with patch("backend.tts.synthesize_speech_provider", return_value=fake_wav):
            for i in range(3):
                r = client.post("/api/tts", json={"text": f"Step {i}"})
                assert r.status_code == 200

            # 4th request exceeds rate limit of 3/min
            r4 = client.post("/api/tts", json={"text": "Step 4"})
            assert r4.status_code == 429
            assert "Rate limit exceeded" in r4.json()["detail"]


def test_11_direction_prefix_applied_correctly_per_position():
    """Vocal directions from TTS_DIRECTION_FIRST, TTS_DIRECTION, and TTS_DIRECTION_LAST
    are correctly routed based on step position."""
    from backend.tts import clear_cache
    clear_cache()
    fake_wav = pcm_to_wav(make_dummy_pcm(0.2), sample_rate=24000)
    env_vars = {
        "TTS_PROVIDER": "groq",
        "GROQ_API_KEY": "gsk_fake_groq_key_for_test",
        "TTS_DIRECTION": "playfully",
        "TTS_DIRECTION_FIRST": "cheerful",
        "TTS_DIRECTION_LAST": "warmly",
    }
    with patch.dict(os.environ, env_vars):
        with patch("backend.tts._call_groq_speech_single", return_value=fake_wav) as mock_groq:
            # First position
            resp_first = client.post("/api/tts", json={"text": "Let us begin step one.", "position": "first"})
            assert resp_first.status_code == 200
            assert mock_groq.call_args[0][0].startswith("[cheerful] ")

            # Middle position (default)
            resp_mid = client.post("/api/tts", json={"text": "Now differentiate the inner term.", "position": "middle"})
            assert resp_mid.status_code == 200
            assert mock_groq.call_args[0][0].startswith("[playfully] ")

            # Last position
            resp_last = client.post("/api/tts", json={"text": "And that is our final result.", "position": "last"})
            assert resp_last.status_code == 200
            assert mock_groq.call_args[0][0].startswith("[warmly] ")


def test_12_invalid_direction_ignored():
    """Invalid directions (not matching ^[a-z]+( [a-z]+)?$) are ignored and clean text is sent."""
    fake_wav = pcm_to_wav(make_dummy_pcm(0.2), sample_rate=24000)
    env_vars = {
        "TTS_PROVIDER": "groq",
        "GROQ_API_KEY": "gsk_fake_groq_key_for_test",
        "TTS_DIRECTION": "CHEERFUL 123 INVALID!",
    }
    with patch.dict(os.environ, env_vars):
        with patch("backend.tts._call_groq_speech_single", return_value=fake_wav) as mock_groq:
            resp = client.post("/api/tts", json={"text": "Solve for the derivative.", "position": "middle"})
            assert resp.status_code == 200
            # Must not contain brackets
            called_text = mock_groq.call_args[0][0]
            assert not called_text.startswith("[")
            assert called_text == "Solve for the derivative."


def test_13_client_response_never_contains_direction_text():
    """Client receives binary WAV audio, never bracketed direction text or prompt metadata."""
    fake_wav = pcm_to_wav(make_dummy_pcm(0.3), sample_rate=24000)
    env_vars = {
        "TTS_PROVIDER": "groq",
        "GROQ_API_KEY": "gsk_fake_groq_key_for_test",
        "TTS_DIRECTION": "cheerful",
    }
    with patch.dict(os.environ, env_vars):
        with patch("backend.tts._call_groq_speech_single", return_value=fake_wav):
            resp = client.post("/api/tts", json={"text": "Good work on this algebra problem.", "position": "middle"})
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "audio/wav"
            assert resp.content.startswith(b"RIFF")
            assert b"[cheerful]" not in resp.content


def test_14_chunking_at_limit_repeats_direction_and_joins_valid_wav():
    """Inputs exceeding the 200-char limit are chunked at sentence/word boundaries,
    direction is repeated on every chunk, and output WAVs are joined into a single valid file."""
    chunk1_wav = pcm_to_wav(make_dummy_pcm(0.5, sample_rate=24000), sample_rate=24000)
    chunk2_wav = pcm_to_wav(make_dummy_pcm(0.7, sample_rate=24000), sample_rate=24000)
    chunks_sent = []

    def mock_call(chunk_text, voice, timeout):
        chunks_sent.append(chunk_text)
        return chunk1_wav if len(chunks_sent) == 1 else chunk2_wav

    long_text = (
        "Alright, let us break this one down together with the chain rule. "
        "We have got an outer function wrapping an inner function, so taking derivatives step by step simplifies the whole expression cleanly."
    )
    assert len(long_text) > 190  # With [cheerful] it exceeds 200 chars

    with patch("backend.tts._call_groq_speech_single", side_effect=mock_call):
        from backend.tts import synthesize_speech_groq
        joined_wav = synthesize_speech_groq(long_text, "autumn", 8.0, direction="cheerful")

        assert len(chunks_sent) == 2
        for chunk in chunks_sent:
            assert len(chunk) <= 200
            assert chunk.startswith("[cheerful] ")

        # Validate joined WAV
        with wave.open(io.BytesIO(joined_wav), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 24000
            assert wf.getnframes() == int((0.5 + 0.7) * 24000)


def test_15_cache_key_differs_by_voice_and_direction():
    """Cache keys differ by voice and direction, preventing cross-voice or cross-direction cache pollution."""
    from backend.tts import get_cache_key
    text = "Find the slope of the tangent line."
    k1 = get_cache_key("canopylabs/orpheus-v1-english", "autumn", text, "cheerful")
    k2 = get_cache_key("canopylabs/orpheus-v1-english", "autumn", text, "playfully")
    k3 = get_cache_key("canopylabs/orpheus-v1-english", "troy", text, "cheerful")
    k4 = get_cache_key("canopylabs/orpheus-v1-english", "autumn", text, "")

    assert len({k1, k2, k3, k4}) == 4  # All 4 keys must be distinct


def test_16_tts_circuit_breaker_skips_failed_provider():
    """Circuit breaker skips an open provider in ~0ms after quota exhaustion."""
    from backend.tts import circuit_breaker

    circuit_breaker.reset()
    assert circuit_breaker.is_available("gemini") is True

    # Record quota failure
    circuit_breaker.record_failure("gemini", "RESOURCE_EXHAUSTED 429", is_quota=True, retry_delay=300)
    assert circuit_breaker.is_available("gemini") is False

    # Immediate check returns False without delay
    t0 = time.time()
    for _ in range(100):
        assert circuit_breaker.is_available("gemini") is False
    elapsed = time.time() - t0
    assert elapsed < 0.05  # 100 checks took less than 50ms


def test_17_tts_provider_chain_falls_back_to_groq_when_gemini_fails():
    """When Gemini raises quota/error, chain falls back to Groq and sets response headers."""
    fake_wav = pcm_to_wav(make_dummy_pcm(0.4), sample_rate=24000)
    with patch("backend.tts.synthesize_speech_gemini", side_effect=RuntimeError("RESOURCE_EXHAUSTED 429")):
        with patch("backend.tts.synthesize_speech_groq", return_value=fake_wav) as mock_groq:
            resp = client.post("/api/tts", json={"text": "Differentiate x squared."})
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "audio/wav"
            assert resp.headers["x-tts-provider"] == "groq"
            assert resp.headers["x-tts-attempts"] == "2"
            mock_groq.assert_called_once()


def test_18_tts_all_providers_failed_returns_503_browser_fallback():
    """When all providers in chain fail, endpoint returns 503 with fallback=browser JSON."""
    with patch("backend.tts.synthesize_speech_gemini", side_effect=RuntimeError("RESOURCE_EXHAUSTED 429")):
        with patch("backend.tts.synthesize_speech_groq", side_effect=RuntimeError("Groq 429 quota")):
            resp = client.post("/api/tts", json={"text": "Compute integral of cos(x)."})
            assert resp.status_code == 503
            assert resp.headers["content-type"] == "application/json"
            assert resp.headers["x-tts-provider"] == "none"
            data = resp.json()
            assert data["fallback"] == "browser"
            assert "reason" in data


def test_19_canonical_wav_normalization_fixes_stream_chunks():
    """normalize_to_canonical_wav repairs streaming WAV with 0xffffffff chunk sizes to canonical 44-byte WAV."""
    import struct
    from backend.tts import normalize_to_canonical_wav

    pcm = make_dummy_pcm(0.5, sample_rate=24000)
    # Construct streaming RIFF chunk with 0xffffffff
    streaming_header = (
        b"RIFF" + struct.pack("<I", 0xFFFFFFFF) + b"WAVE" +
        b"fmt " + struct.pack("<I", 16) + struct.pack("<HHIIHH", 1, 1, 24000, 48000, 2, 16) +
        b"data" + struct.pack("<I", 0xFFFFFFFF)
    )
    corrupt_stream = streaming_header + pcm

    # Passing through normalize_to_canonical_wav fixes it
    fixed_wav = normalize_to_canonical_wav(corrupt_stream)
    assert len(fixed_wav) == 44 + len(pcm)
    with wave.open(io.BytesIO(fixed_wav), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 24000
        assert wf.getnframes() == len(pcm) // 2


