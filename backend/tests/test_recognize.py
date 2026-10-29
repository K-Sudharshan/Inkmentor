import base64
import json
import os
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

os.environ["TEST_MODE"] = "true"
os.environ["LLM_PROVIDER"] = "gemini"
os.environ["LLM_MODEL"] = "gemini-2.5-flash"
os.environ["LLM_API_KEY"] = "super_secret_test_key_12345"

from backend.main import app
from backend.recognize import parse_image_data, recognize_image
from backend.schemas import RecognizeRequest

# Valid 1x1 PNG and JPEG sample bytes
TINY_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
    b"\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
)
TINY_PNG_B64 = base64.b64encode(TINY_PNG_BYTES).decode("ascii")

TINY_JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00\xff\xc0\x00\x0b"
    b"\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00"
    b"\x00?\x00\xbf\x00\xff\xd9"
)
TINY_JPEG_B64 = base64.b64encode(TINY_JPEG_BYTES).decode("ascii")

client = TestClient(app)


def test_1_valid_tiny_png_returns_full_response():
    """1. Valid tiny PNG returns the full response matching the exact contract."""
    mock_payload = {
        "readable": True,
        "latex": "y = \\sin(3x^2)",
        "question_text": "Differentiate y = sin(3x^2)",
        "note": "",
    }
    with patch("backend.recognize.call_vision_llm", return_value=json.dumps(mock_payload)):
        res = client.post(
            "/api/recognize",
            json={"image_base64": TINY_PNG_B64, "media_type": "image/png"},
        )
        assert res.status_code == 200
        data = res.json()
        timing = data.pop("timing", None)
        assert data == {
            "readable": True,
            "latex": "y = \\sin(3x^2)",
            "question_text": "Differentiate y = sin(3x^2)",
            "needs_confirmation": True,
            "note": "",
        }


def test_2_data_prefix_stripped():
    """2. Data: prefix in image_base64 is stripped and decoded correctly."""
    mock_payload = {
        "readable": True,
        "latex": "x^2",
        "question_text": "x^2",
        "note": "",
    }
    with patch("backend.recognize.call_vision_llm", return_value=json.dumps(mock_payload)) as mock_llm:
        res = client.post(
            "/api/recognize",
            json={"image_base64": f"data:image/png;base64,{TINY_PNG_B64}", "media_type": "image/png"},
        )
        assert res.status_code == 200
        assert res.json()["readable"] is True
        # Verify raw bytes passed to LLM match TINY_PNG_BYTES
        mock_llm.assert_called_once()
        passed_bytes = mock_llm.call_args[0][0]
        assert passed_bytes == TINY_PNG_BYTES


def test_3_bad_base64_is_422():
    """3. Bad base64 returns 422 error."""
    res = client.post(
        "/api/recognize",
        json={"image_base64": "not_valid_base64_symbols!!!", "media_type": "image/png"},
    )
    assert res.status_code == 422
    assert "Invalid base64" in res.json()["detail"]


def test_4_image_gif_is_422():
    """4. Unsupported media_type like image/gif returns 422."""
    res = client.post(
        "/api/recognize",
        json={"image_base64": TINY_PNG_B64, "media_type": "image/gif"},
    )
    assert res.status_code == 422


def test_5_magic_byte_mismatch_is_422():
    """5. Declared media_type mismatch with actual magic bytes returns 422."""
    # Declaring image/png but providing JPEG magic bytes
    res = client.post(
        "/api/recognize",
        json={"image_base64": TINY_JPEG_B64, "media_type": "image/png"},
    )
    assert res.status_code == 422
    assert "Magic bytes do not match declared media_type image/png" in res.json()["detail"]

    # Declaring image/jpeg but providing PNG magic bytes
    res2 = client.post(
        "/api/recognize",
        json={"image_base64": TINY_PNG_B64, "media_type": "image/jpeg"},
    )
    assert res2.status_code == 422
    assert "Magic bytes do not match declared media_type image/jpeg" in res2.json()["detail"]


def test_6_oversized_is_422(monkeypatch):
    """6. Image exceeding MAX_IMAGE_BYTES returns 422."""
    monkeypatch.setenv("MAX_IMAGE_BYTES", "50")
    res = client.post(
        "/api/recognize",
        json={"image_base64": TINY_PNG_B64, "media_type": "image/png"},
    )
    assert res.status_code == 422
    assert "exceeds maximum allowed size" in res.json()["detail"]


def test_7_readable_false_path():
    """7. Blank/illegible image returns readable=false with empty latex and question_text."""
    mock_payload = {
        "readable": False,
        "latex": "some_accidental_hallucination",
        "question_text": "accidental_text",
        "note": "Image appears blank or contains no legible math.",
    }
    with patch("backend.recognize.call_vision_llm", return_value=json.dumps(mock_payload)):
        res = client.post(
            "/api/recognize",
            json={"image_base64": TINY_PNG_B64, "media_type": "image/png"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["readable"] is False
        assert data["latex"] == ""
        assert data["question_text"] == ""
        assert data["needs_confirmation"] is True
        assert "blank" in data["note"].lower()


def test_8_invalid_json_then_valid_triggers_exactly_2_llm_calls():
    """8. Invalid JSON on attempt 1 followed by valid JSON on attempt 2 triggers exactly 2 calls."""
    good_payload = {
        "readable": True,
        "latex": "x^2 + 1",
        "question_text": "x^2 + 1",
        "note": "",
    }
    mock_llm = MagicMock(side_effect=["Not JSON output at all", json.dumps(good_payload)])
    with patch("backend.recognize.call_vision_llm", mock_llm):
        res = client.post(
            "/api/recognize",
            json={"image_base64": TINY_PNG_B64, "media_type": "image/png"},
        )
        assert res.status_code == 200
        assert mock_llm.call_count == 2
        assert res.json()["latex"] == "x^2 + 1"


def test_9_invalid_twice_is_502():
    """9. Invalid LLM output twice returns 502 Bad Gateway."""
    mock_llm = MagicMock(side_effect=["Invalid JSON attempt 1", "Invalid JSON attempt 2"])
    with patch("backend.recognize.call_vision_llm", mock_llm):
        res = client.post(
            "/api/recognize",
            json={"image_base64": TINY_PNG_B64, "media_type": "image/png"},
        )
        assert res.status_code == 502
        assert mock_llm.call_count == 2
        assert "Vision provider error" in res.json()["detail"]


def test_10_provider_error_is_502_with_no_key_in_body(monkeypatch):
    """10. Upstream provider failure returns 502 with no API key in the response body."""
    secret_key = "super_secret_test_key_12345"
    monkeypatch.setenv("LLM_API_KEY", secret_key)
    mock_llm = MagicMock(side_effect=RuntimeError(f"Google GenAI 500 error key={secret_key} connection lost"))
    with patch("backend.recognize.call_vision_llm", mock_llm):
        res = client.post(
            "/api/recognize",
            json={"image_base64": TINY_PNG_B64, "media_type": "image/png"},
        )
        assert res.status_code == 502
        assert secret_key not in res.text
        assert "[REDACTED]" in res.text

