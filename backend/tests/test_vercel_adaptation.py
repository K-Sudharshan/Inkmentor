import os
import tempfile
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.main import app, get_client_ip
from backend.tts import clear_cache, pcm_to_wav
from backend.memory import get_seed_pages, _SEEDED_PAGES_CACHE

client = TestClient(app)


def make_dummy_pcm(duration_sec: float = 0.2, sample_rate: int = 24000) -> bytes:
    num_samples = int(duration_sec * sample_rate)
    return b"\x00\x00" * num_samples


@pytest.fixture(autouse=True)
def reset_state():
    clear_cache()
    yield
    clear_cache()


def test_kill_switch_gemini_goes_straight_to_groq():
    """With TTS_DISABLE_GEMINI=true, TTS skips Gemini with 0 calls and goes straight to Groq."""
    fake_wav = pcm_to_wav(make_dummy_pcm(0.2), sample_rate=24000)
    env_vars = {
        "TTS_DISABLE_GEMINI": "true",
        "GROQ_API_KEY": "gsk_test_mock_key",
    }
    with patch.dict(os.environ, env_vars):
        with patch("backend.tts.synthesize_speech_gemini") as mock_gemini:
            with patch("backend.tts.synthesize_speech_groq", return_value=fake_wav) as mock_groq:
                resp = client.post("/api/tts", json={"text": "Step 1: Simplify terms."})
                assert resp.status_code == 200
                assert resp.headers["x-tts-provider"] == "groq"
                assert resp.headers["x-tts-attempts"] == "1"
                # Gemini must never have been called
                mock_gemini.assert_not_called()
                mock_groq.assert_called_once()


def test_kill_switch_both_disabled_falls_back_to_browser():
    """With both Gemini and Groq disabled, returns 503 fallback to browser."""
    env_vars = {
        "TTS_DISABLE_GEMINI": "true",
        "TTS_DISABLE_GROQ": "true",
    }
    with patch.dict(os.environ, env_vars):
        with patch("backend.tts.synthesize_speech_gemini") as mock_gemini:
            with patch("backend.tts.synthesize_speech_groq") as mock_groq:
                resp = client.post("/api/tts", json={"text": "Step 1: Simplify terms."})
                assert resp.status_code == 503
                data = resp.json()
                assert data["fallback"] == "browser"
                mock_gemini.assert_not_called()
                mock_groq.assert_not_called()


def test_proxy_ip_handling_untrusted_by_default():
    """When TRUST_PROXY_HEADERS is false or unset, x-forwarded-for header is ignored."""
    env_vars = {"TRUST_PROXY_HEADERS": "false"}
    with patch.dict(os.environ, env_vars):
        fake_wav = pcm_to_wav(make_dummy_pcm(0.1), sample_rate=24000)
        with patch("backend.main.generate_tts_wav", return_value=fake_wav) as mock_gen:
            headers = {"x-forwarded-for": "203.0.113.195, 10.0.0.1"}
            resp = client.post("/api/tts", json={"text": "Verify proxy ip"}, headers=headers)
            assert resp.status_code == 200
            passed_ip = mock_gen.call_args[1]["client_ip"]
            assert passed_ip != "203.0.113.195"


def test_proxy_ip_handling_trusted_when_flag_set():
    """When TRUST_PROXY_HEADERS=true, x-forwarded-for / x-real-ip are trusted."""
    env_vars = {"TRUST_PROXY_HEADERS": "true"}
    with patch.dict(os.environ, env_vars):
        fake_wav = pcm_to_wav(make_dummy_pcm(0.1), sample_rate=24000)
        with patch("backend.main.generate_tts_wav", return_value=fake_wav) as mock_gen:
            headers = {"x-forwarded-for": "198.51.100.42, 10.0.0.2"}
            resp = client.post("/api/tts", json={"text": "Verify proxy ip trusted"}, headers=headers)
            assert resp.status_code == 200
            passed_ip = mock_gen.call_args[1]["client_ip"]
            assert passed_ip == "198.51.100.42"

        # Check x-real-ip fallback when x-forwarded-for is missing
        with patch("backend.main.generate_tts_wav", return_value=fake_wav) as mock_gen2:
            headers = {"x-real-ip": "198.51.100.88"}
            resp = client.post("/api/tts", json={"text": "Verify real ip trusted"}, headers=headers)
            assert resp.status_code == 200
            passed_ip = mock_gen2.call_args[1]["client_ip"]
            assert passed_ip == "198.51.100.88"



def test_lazy_initialization_worker_pool_and_memory():
    """SymPy worker pool and Memory index are initialized lazily on demand."""
    from backend import verify
    # Reset pool
    verify.shutdown_sympy_worker_pool()
    assert verify._global_pool is None

    # Getting worker pool lazily instantiates the object
    pool = verify.get_worker_pool()
    assert pool is not None
    assert verify._global_pool is pool

    # Memory pages load lazily and return seeded list
    pages = get_seed_pages()
    assert isinstance(pages, list)
    assert len(pages) > 0


def test_health_endpoint_flags_and_deep_check():
    """GET /api/health returns status and flags; /api/health/deep verifies external LLM when enabled."""
    resp = client.get("/api/health?verbose=true")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "keys" in data
    assert "gemini" in data["keys"]
    assert "groq" in data["keys"]
    assert "memory_index_loaded" in data
    assert "tts_disabled" in data

    # Deep health check disabled by default
    resp_deep_off = client.get("/api/health/deep")
    assert resp_deep_off.status_code == 403

    # Deep health check enabled
    with patch.dict(os.environ, {"ENABLE_DEEP_HEALTH": "true"}):
        with patch("backend.llm.call_llm", return_value="pong"):
            resp_deep_on = client.get("/api/health/deep")
            assert resp_deep_on.status_code == 200
            deep_data = resp_deep_on.json()
            assert deep_data["status"] == "ok"
            assert deep_data["gemini"] == "connected"
            assert "latency_ms" in deep_data


def test_static_routes_serve_index_and_font():
    """Static routes serve index.html and font files locally."""
    resp_root = client.get("/")
    assert resp_root.status_code == 200
    assert "text/html" in resp_root.headers.get("content-type", "")

    resp_font = client.get("/fonts/Caveat-Regular.ttf")
    assert resp_font.status_code == 200
    assert resp_font.headers.get("content-type") == "font/ttf"


def test_dual_routes_accessible_without_api_prefix():
    """Endpoints are reachable both with /api prefix and without (handles Vercel path stripping)."""
    resp_health_api = client.get("/api/health?verbose=true")
    assert resp_health_api.status_code == 200

    resp_health_stripped = client.get("/health?verbose=true")
    assert resp_health_stripped.status_code == 200
    assert resp_health_stripped.json()["status"] == "ok"

    resp_tts_status_stripped = client.get("/tts/status")
    assert resp_tts_status_stripped.status_code == 200


def test_middleware_recovers_path_from_x_matched_path():
    """Middleware rewrites scope path if Vercel passes /api/index.py."""
    headers = {"x-matched-path": "/api/health?verbose=true"}
    resp = client.get("/api/index.py", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_resilient_env_defaults_and_gemini_key_fallback():
    """_get_required_env and validate_llm_env fall back to gemini defaults and GEMINI_API_KEY."""
    from backend.llm import _get_required_env, validate_llm_env

    # Clean env with only GEMINI_API_KEY set
    clean_env = {
        "LLM_PROVIDER": "",
        "LLM_MODEL": "",
        "LLM_API_KEY": "",
        "GEMINI_API_KEY": "AIzaSy_fallback_key",
    }
    with patch.dict(os.environ, clean_env):
        assert _get_required_env("LLM_PROVIDER") == "gemini"
        assert _get_required_env("LLM_MODEL") in ("gemini-3-flash-preview", "gemini-3.5-flash-lite")
        assert _get_required_env("LLM_API_KEY") == "AIzaSy_fallback_key"
        # Must not raise
        validate_llm_env()

