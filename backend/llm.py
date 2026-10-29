import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=False)


def _get_required_env(var_name: str) -> str:
    if var_name == "LLM_PROVIDER":
        return (os.environ.get("LLM_PROVIDER") or "gemini").strip()
    if var_name == "LLM_MODEL":
        val = (os.environ.get("LLM_MODEL") or "gemini-3.5-flash").strip()
        # Automatically map deprecated or overloaded preview models to active gemini-3.5-flash
        if val in ("gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-flash-lite") or "2.5-flash" in val or "2.0-flash" in val or "3.5-flash-lite" in val:
            return "gemini-3.5-flash"
        return val
    if var_name == "LLM_API_KEY":
        val = os.environ.get("LLM_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not val or not val.strip():
            raise RuntimeError("Missing required environment variable: LLM_API_KEY (or GEMINI_API_KEY)")
        return val.strip()
    val = os.environ.get(var_name)
    if not val or not val.strip():
        raise RuntimeError(f"Missing required environment variable: {var_name}")
    return val.strip()


def validate_llm_env() -> None:
    """Validates that all required LLM environment variables are present."""
    provider = _get_required_env("LLM_PROVIDER").lower()
    if provider != "gemini":
        raise RuntimeError(f"Unsupported LLM_PROVIDER: {provider}. Expected 'gemini'.")
    _get_required_env("LLM_API_KEY")
    _get_required_env("LLM_MODEL")


import threading
import time
from typing import Any, Dict, Optional, Tuple

_client_lock = threading.Lock()
_cached_client: Optional[genai.Client] = None
_cached_api_key: Optional[str] = None
_last_vision_meta = threading.local()


def get_last_vision_meta() -> Optional[Dict[str, Any]]:
    return getattr(_last_vision_meta, "val", None)

USE_OPTIMIZED_LLM_CONFIG = os.getenv("USE_OPTIMIZED_LLM_CONFIG", "true").lower() in ("true", "1", "yes")
LLM_MAX_OUTPUT_TOKENS = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "2048"))


def get_genai_client(api_key: str) -> genai.Client:
    """Returns a reused genai.Client instance to avoid rebuilding HTTP transport per request."""
    global _cached_client, _cached_api_key
    with _client_lock:
        if _cached_client is None or _cached_api_key != api_key:
            _cached_client = genai.Client(api_key=api_key)
            _cached_api_key = api_key
        return _cached_client


def call_llm_with_meta(system: str, user: str) -> Tuple[str, Dict[str, Any]]:
    """Calls the configured LLM provider using its official SDK and returns text and metadata."""
    provider = _get_required_env("LLM_PROVIDER").lower()
    if provider != "gemini":
        raise RuntimeError(f"Unsupported LLM_PROVIDER: {provider}. Expected 'gemini'.")

    api_key = _get_required_env("LLM_API_KEY")
    model_name = _get_required_env("LLM_MODEL")

    t0 = time.time()
    try:
        client = get_genai_client(api_key)
        if USE_OPTIMIZED_LLM_CONFIG:
            try:
                config = types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=0.0,
                    max_output_tokens=LLM_MAX_OUTPUT_TOKENS,
                    thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL),
                )
            except Exception:
                config = types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=0.0,
                    max_output_tokens=LLM_MAX_OUTPUT_TOKENS,
                )
        else:
            config = types.GenerateContentConfig(
                system_instruction=system,
                temperature=0.0,
            )

        try:
            response = client.models.generate_content(
                model=model_name,
                contents=user,
                config=config,
            )
        except Exception as api_err:
            err_str = str(api_err).lower()
            if "thinking" in err_str or "budget" in err_str or "invalid_argument" in err_str or "400" in err_str:
                # Fallback without thinking_config if model rejects thinking settings
                fallback_config = types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=0.0,
                    max_output_tokens=LLM_MAX_OUTPUT_TOKENS,
                )
                response = client.models.generate_content(
                    model=model_name,
                    contents=user,
                    config=fallback_config,
                )
            elif (
                "404" in err_str
                or "not found" in err_str
                or "no longer available" in err_str
                or "429" in err_str
                or "quota" in err_str
                or "resource_exhausted" in err_str
                or "503" in err_str
            ):
                alt_model = "gemini-3.5-flash" if model_name != "gemini-3.5-flash" else "gemini-3.1-flash-lite-preview"
                response = client.models.generate_content(
                    model=alt_model,
                    contents=user,
                    config=config,
                )
            else:
                raise
        duration_ms = round((time.time() - t0) * 1000.0, 2)
        if not response.text:
            raise RuntimeError("LLM returned an empty response")

        meta = {
            "duration_ms": duration_ms,
            "input_tokens": None,
            "output_tokens": None,
            "thinking_tokens": None,
            "total_tokens": None,
        }
        if response.usage_metadata:
            meta["input_tokens"] = getattr(response.usage_metadata, "prompt_token_count", None)
            meta["output_tokens"] = getattr(response.usage_metadata, "candidates_token_count", None)
            meta["thinking_tokens"] = getattr(response.usage_metadata, "thoughts_token_count", None)
            meta["total_tokens"] = getattr(response.usage_metadata, "total_token_count", None)

        return response.text, meta
    except Exception as exc:
        err_msg = str(exc)
        if api_key in err_msg:
            err_msg = err_msg.replace(api_key, "[REDACTED]")
        raise RuntimeError(f"LLM provider call failed: {type(exc).__name__}: {err_msg}") from None


def call_llm(system: str, user: str) -> str:
    """Calls the configured LLM provider using its official SDK.
    Implemented for gemini using google-genai SDK."""
    text, _ = call_llm_with_meta(system, user)
    return text


def call_vision_llm_with_meta(
    image_bytes: bytes,
    mime_type: str = "image/png",
    prompt: str = "Transcribe the handwritten math in this image into clean LaTeX. Return ONLY the LaTeX expression without markdown fences or commentary.",
) -> Tuple[str, Dict[str, Any]]:
    """Calls Gemini vision API and returns text and timing/token metadata."""
    provider = _get_required_env("LLM_PROVIDER").lower()
    if provider != "gemini":
        raise RuntimeError(f"Unsupported LLM_PROVIDER: {provider}. Expected 'gemini'.")

    api_key = _get_required_env("LLM_API_KEY")
    model_name = (os.environ.get("LLM_VISION_MODEL") or _get_required_env("LLM_MODEL")).strip()
    vision_max_tokens = int(os.environ.get("LLM_VISION_MAX_OUTPUT_TOKENS", "300"))
    is_json = "json" in prompt.lower() or prompt.strip().endswith("}")

    t0 = time.time()
    try:
        client = get_genai_client(api_key)
        part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        gen_kwargs = {
            "temperature": 0.0,
            "max_output_tokens": vision_max_tokens,
        }
        if is_json:
            gen_kwargs["response_mime_type"] = "application/json"

        if USE_OPTIMIZED_LLM_CONFIG:
            try:
                config = types.GenerateContentConfig(
                    **gen_kwargs,
                    thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL),
                )
            except Exception:
                config = types.GenerateContentConfig(**gen_kwargs)
        else:
            config = types.GenerateContentConfig(**gen_kwargs)

        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[prompt, part],
                config=config,
            )
        except Exception as api_err:
            err_str = str(api_err).lower()
            if "thinking" in err_str or "budget" in err_str or "invalid_argument" in err_str or "400" in err_str:
                fallback_config = types.GenerateContentConfig(**gen_kwargs)
                response = client.models.generate_content(
                    model=model_name,
                    contents=[prompt, part],
                    config=fallback_config,
                )
            elif (
                "404" in err_str
                or "not found" in err_str
                or "no longer available" in err_str
                or "429" in err_str
                or "quota" in err_str
                or "resource_exhausted" in err_str
                or "503" in err_str
            ):
                alt_model = "gemini-3.5-flash" if model_name != "gemini-3.5-flash" else "gemini-3.1-flash-lite-preview"
                response = client.models.generate_content(
                    model=alt_model,
                    contents=[prompt, part],
                    config=config,
                )
            else:
                raise
        duration_ms = round((time.time() - t0) * 1000.0, 2)
        if not response.text:
            raise RuntimeError("Vision model returned an empty response")

        meta = {
            "duration_ms": duration_ms,
            "input_tokens": None,
            "output_tokens": None,
            "thinking_tokens": None,
            "total_tokens": None,
        }
        if response.usage_metadata:
            meta["input_tokens"] = getattr(response.usage_metadata, "prompt_token_count", None)
            meta["output_tokens"] = getattr(response.usage_metadata, "candidates_token_count", None)
            meta["thinking_tokens"] = getattr(response.usage_metadata, "thoughts_token_count", None)
            meta["total_tokens"] = getattr(response.usage_metadata, "total_token_count", None)

        _last_vision_meta.val = meta
        return response.text, meta
    except Exception as exc:
        err_msg = str(exc)
        if api_key in err_msg:
            err_msg = err_msg.replace(api_key, "[REDACTED]")
        raise RuntimeError(f"LLM provider vision call failed: {type(exc).__name__}: {err_msg}") from None


def call_vision_llm(
    image_bytes: bytes,
    mime_type: str = "image/png",
    prompt: str = "Transcribe the handwritten math in this image into clean LaTeX. Return ONLY the LaTeX expression without markdown fences or commentary.",
) -> str:
    """Calls Gemini vision API to transcribe handwritten math from image bytes."""
    text, meta = call_vision_llm_with_meta(image_bytes, mime_type=mime_type, prompt=prompt)
    _last_vision_meta.val = meta
    return text


def call_embedding(
    text: str,
    model_name: str | None = None,
) -> list[float]:
    """Calls Gemini embedding API to embed text into a vector."""
    provider = _get_required_env("LLM_PROVIDER").lower()
    if provider != "gemini":
        raise RuntimeError(f"Unsupported LLM_PROVIDER: {provider}. Expected 'gemini'.")

    api_key = _get_required_env("LLM_API_KEY")
    target_model = model_name or os.environ.get("LLM_EMBEDDING_MODEL", "gemini-embedding-001")

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.embed_content(
            model=target_model,
            contents=text,
        )
        if not response.embeddings or not response.embeddings[0].values:
            raise RuntimeError("Embedding model returned an empty response")
        return list(response.embeddings[0].values)
    except Exception as exc:
        err_msg = str(exc)
        if api_key in err_msg:
            err_msg = err_msg.replace(api_key, "[REDACTED]")
        raise RuntimeError(f"LLM provider embedding call failed: {type(exc).__name__}: {err_msg}") from None

