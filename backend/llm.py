import os
from google import genai
from google.genai import types


def _get_required_env(var_name: str) -> str:
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


def call_llm(system: str, user: str) -> str:
    """Calls the configured LLM provider using its official SDK.
    Implemented for gemini using google-genai SDK."""
    provider = _get_required_env("LLM_PROVIDER").lower()
    if provider != "gemini":
        raise RuntimeError(f"Unsupported LLM_PROVIDER: {provider}. Expected 'gemini'.")

    api_key = _get_required_env("LLM_API_KEY")
    model_name = _get_required_env("LLM_MODEL")

    try:
        client = genai.Client(api_key=api_key)
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.0,
        )
        response = client.models.generate_content(
            model=model_name,
            contents=user,
            config=config,
        )
        if not response.text:
            raise RuntimeError("LLM returned an empty response")
        return response.text
    except Exception as exc:
        # Sanitize exception message so keys are never leaked
        err_msg = str(exc)
        if api_key in err_msg:
            err_msg = err_msg.replace(api_key, "[REDACTED]")
        raise RuntimeError(f"LLM provider call failed: {type(exc).__name__}: {err_msg}") from None


def call_vision_llm(
    image_bytes: bytes,
    mime_type: str = "image/png",
    prompt: str = "Transcribe the handwritten math in this image into clean LaTeX. Return ONLY the LaTeX expression without markdown fences or commentary.",
) -> str:
    """Calls Gemini vision API to transcribe handwritten math from image bytes."""
    provider = _get_required_env("LLM_PROVIDER").lower()
    if provider != "gemini":
        raise RuntimeError(f"Unsupported LLM_PROVIDER: {provider}. Expected 'gemini'.")

    api_key = _get_required_env("LLM_API_KEY")
    model_name = _get_required_env("LLM_MODEL")

    try:
        client = genai.Client(api_key=api_key)
        part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        response = client.models.generate_content(
            model=model_name,
            contents=[prompt, part],
            config=types.GenerateContentConfig(temperature=0.0),
        )
        if not response.text:
            raise RuntimeError("Vision model returned an empty response")
        return response.text
    except Exception as exc:
        err_msg = str(exc)
        if api_key in err_msg:
            err_msg = err_msg.replace(api_key, "[REDACTED]")
        raise RuntimeError(f"LLM provider vision call failed: {type(exc).__name__}: {err_msg}") from None


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

